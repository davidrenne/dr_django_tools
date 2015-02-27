import tempfile
from urlparse import urlparse
import math
import fnmatch
import os
import importlib
import time
import datetime
from HTMLParser import HTMLParser

import requests
from pycountry import countries
from fuzzywuzzy import process
import ftputil
from unidecode import unidecode
from PIL import Image
from django.conf import settings
from django.core.urlresolvers import reverse
from cities.models import Country, Region, City


THUMBNAIL_DIMS = (120, 70)  # preferred width/height of thumbnails

IMAGE_TYPE_GENERAL = 0
IMAGE_TYPE_VENDOR_THUMB = 1
IMAGE_TYPE_PHOTO_THUMB = 2
IMAGE_TYPE_SELECTED_THUMB = 3
IMAGE_TYPE_EXTENDED = 4

def td2HHMMSSstr(td):
    '''Convert timedelta objects to a HH:MM:SS string with (+/-) sign'''
    if td < datetime.timedelta(seconds=0):
        sign='-'
        td = -td
    else:
        sign = ''
    tdhours, rem = divmod(td.total_seconds(), 3600)
    tdminutes, tdseconds = divmod(rem, 60)
    if int(tdhours) > 0:
        tdstr = '{}{:}:'.format(sign, int(tdhours))
    else:
        tdstr = '{}'.format(sign)
    tdstr = tdstr + '{:02d}:{:02d}'.format(int(tdminutes), int(tdseconds))
    return tdstr


def fetchfile(source):
    '''Return an open file object.  If the source contains a url then the
    requests library is used to download the content and store as a
    temporary file and return that temporary file.
    '''

    if '://' in source:
        ignored, filename = tempfile.mkstemp()
        with open(filename, 'wb') as f:
            r = requests.get(source)
            f.write(r.content)
        return open(filename, 'rb')

    return open(source, 'rb')


def moduleitem(dottedpath):
    mname = '.'.join(dottedpath.split('.')[:-1])
    itemname = dottedpath.split('.')[-1]
    module_ = importlib.import_module(mname)
    item = getattr(module_, itemname)
    return item


def image_path(type_, id, full=True):
    short = '%012i' % int(id)
    target = '%s/%s/%s/%s.jpg' % (type_, short[:4], short[4:8], short)
    if full:
        target = os.path.join(settings.IMAGE_DIR, target)
    return target


def update_image(type_, image, url, width=-1, height=-1):
    target = image_path(type_, image.id)
    local = os.path.dirname(target)
    if not os.path.exists(local):
        os.makedirs(local)
    headers = {
    }
    if os.path.exists(target):
        updated = time.ctime(os.path.getmtime(target))
        headers['If-Modified-Since'] = time.strftime('%a, %d %b %Y %H:%M:%S +0000', time.strptime(updated))
    if width != -1:
        grab_and_scale(url, target, width, height)
    else:
        grab(url, target)


country_names = [x.name for x in countries]


def lookup_country_code(name):
    name = name.replace('St. ', 'Saint ')
    real_name = process.extractOne(name, country_names)
    return countries.get(name=real_name[0]).alpha2


class TreeHelper(object):
    def __init__(self, tree):
        self.tree = tree

    @property
    def root(self):
        return self.tree.getroot()

    def xpath_single(self, xp):
        if self.root.xpath(xp):
            return self.root.xpath(xp)[0]
        else:
            return False

    def xpath_text(self, xp):
        node = self.xpath_single(xp)
        if node != False:
            return node.text
        else:
            return ''

    def xpath_attr(self, xp, attr):
        return self.xpath_single(xp).attrib[attr]


class XMLNodeHelper(object):
    def __init__(self, node, namespaces=None):
        self.node = node
        self.namespaces = namespaces

    def xpath_single(self, xp):
        if self.namespaces:
            res = self.node.xpath(xp, namespaces=self.namespaces)
        else:
            res = self.node.xpath(xp)

        if len(res) == 0:
            return None
            
        return res[0]

    def xpath_text(self, xp):
        el = self.xpath_single(xp)
        if el is None:
            return ''
        return el.text

    def xpath_attr(self, xp, attr):
        el = self.xpath_single(xp)
        if el is None:
            return ''
        if attr in el.attrib:
            return el.attrib[attr]
        return ''

    def xpath(self, xp):
        if self.namespaces:
            return self.node.xpath(xp, namespaces=self.namespaces)
        return self.node.xpath(xp)


def grab_to_temp(url):
    handle, filename = tempfile.mkstemp()
    os.close(handle)
    grab(url, filename)
    return filename


def grab(url, target):
    if url.startswith('ftp://'):
        # handle ftp download
        o = urlparse(url)
        pieces = o.netloc.split('@')
        host = pieces[-1]
        parts = [host]
        path = o.path
        if path.startswith('/'):
            path = path[1:]
        if len(pieces) > 1:
            username, password = pieces[0].split(':')
            parts.append(username)
            parts.append(password)
        ftp = ftputil.FTPHost(*parts)
        for filename in ftp.listdir('.'):
            if not fnmatch.fnmatch(filename, path):
                continue
            ftp.download(filename, target)
        return

    headers = {}
    if os.path.exists(target) and os.path.getsize(target) > 0:
        updated = time.ctime(os.path.getmtime(target))
        headers['If-Modified-Since'] = time.strftime(
            '%a, %d %b %Y %H:%M:%S +0000', time.strptime(updated))

    if url.startswith('http'):
        res = requests.get(url, headers=headers, stream=True)
        if res.status_code == 200:
            with open(target, 'wb') as f:
                for chunk in res.iter_content(2048):
                    f.write(chunk)
        elif res.status_code != 304:
            raise IOError('Error (%s) while trying to remotely request: %s'
                          % (res.status_code, url))
    else:
        res = None
        with open(target, 'wb') as fout, open(url, 'rb') as fin:
            chunk = None
            while chunk is None or len(chunk) == 2048:
                chunk = fin.read(2048)
                fout.write(chunk)

    return res


def grab_and_scale(url, target, width, height):
    ignored, tmp1 = tempfile.mkstemp(suffix='.jpg')

    try:
        grab(url, tmp1)
        im = Image.open(tmp1)
        im.thumbnail((width, height), Image.ANTIALIAS)
        im.save(target, "JPEG")
    finally:
        if os.path.exists(tmp1):
            os.remove(tmp1)


def first(query):
    try:
        return query[0]
    except:
        return None


def lookup_location(country_s, region_s=None, city_s=None):
    country = None
    country_opts = [country_s]
    if '/' in country_s:
        country_opts = country_s.split('/')
    for country_s in country_opts:
        if country_s.lower().startswith('us '):
            country_s = 'U.S. ' + country_s[3:]
        if country_s.lower().startswith('st. '):
            country_s = 'Saint ' + country_s[4:]
        if country_s.lower() == 'equador':
            country_s = 'ecuador'
        if country_s == 'USA':
            country_s = 'US'
        if country_s == 'UAE':
            country_s = 'AE'
        if len(country_s) == 2:
            country = first(Country.objects.filter(code=country_s))
        if country is None:
            country = first(Country.objects.filter(slug=country_s))
        if country is None:
            country = first(Country.objects.filter(name__icontains=country_s))
        if country is not None:
            break
    if country is None:
        raise ValueError('Could not find country: ' + country_s)

    if not region_s and not city_s:
        return country

    region = first(Region.objects.filter(code=region_s, country=country))
    if region is None:
        region = first(Region.objects.filter(slug=region_s, country=country))
    if region is None:
        region = first(Region.objects.filter(
            name__icontains=region_s, country=country))
    if region is None:
        q = Region.objects.values('name').filter(country=country)
        values = [x['name'] for x in q.all()]
        if values:
            r = process.extractOne(region_s, values)
            if r is not None and len(r) > 0:
                region = first(Region.objects.filter(
                    name=r[0], country=country))

    if not city_s:
        if region is not None:
            return region
        return country

    city = None
    if region is not None:
        city = first(City.objects.filter(
            slug=city_s, country=country, region=region))
        if city is None:
            city = first(City.objects.filter(
                name__icontains=city_s, country=country, region=region))
        if city is None:
            q = City.objects.values('name').filter(
                country=country, region=region)
            values = [x['name'] for x in q.all()]
            if values:
                r = process.extractOne(city_s, values)[0]
                city = first(City.objects.filter(
                    name=r, country=country, region=region))
    if city is None:
        q = City.objects.values('name').filter(country=country)
        values = [x['name'] for x in q.all()]
        if values:
            r = process.extractOne(city_s, values)
            if r is not None and len(r) > 0:
                city = first(City.objects.filter(name=r[0], country=country))
    if city is None:
        raise ValueError('Could not find city (%s:%i): %s '
                         '[original: %s / %s / %s]'
                         % (region,
                            getattr(region, 'id', -1),
                            city_s, country_s, region_s, city_s))

    return city


def lookup_city(country_s, region_s, city_s):
    country = None
    if country_s == 'USA':
        country_s = 'US'
    if len(country_s) == 2:
        country = first(Country.objects.filter(code=country_s))
    if country is None:
        country = first(Country.objects.filter(slug=country_s))
    if country is None:
        country = first(Country.objects.filter(name__icontains=country_s))
    if country is None:
        raise ValueError('Could not find country: ' + country_s)

    region = first(Region.objects.filter(code=region_s, country=country))
    if region is None:
        region = first(Region.objects.filter(slug=region_s, country=country))
    if region is None:
        region = first(Region.objects.filter(name__icontains=region_s, country=country))
    if region is None:
        values = [x['name'] for x in Region.objects.values('name').filter(country=country).all()]
        if values:
            r = process.extractOne(region_s, values)
            if r is not None and len(r) > 0:
                region = first(Region.objects.filter(name=r[0], country=country))

    city = None
    if region is not None:
        city = first(City.objects.filter(slug=city_s, country=country, region=region))
        if city is None:
            city = first(City.objects.filter(name__icontains=city_s, country=country, region=region))
        if city is None:
            values = [x['name'] for x in City.objects.values('name').filter(country=country, region=region).all()]
            if values:
                possible_city = process.extractOne(city_s, values)
                if possible_city is not None:
                    r = possible_city[0]
                    city = first(City.objects.filter(name=r, country=country, region=region))
    if city is None:
        values = [x['name'] for x in City.objects.values('name').filter(country=country).all()]
        if values:
            r = process.extractOne(city_s, values)
            if r is not None and len(r) > 0:
                city = first(City.objects.filter(name=r[0], country=country))
    if city is None:
        raise ValueError('Could not find city (%s:%i): %s [original: %s / %s / %s]' % (region, getattr(region, 'id', -1), city_s, country_s, region_s, city_s))
    
    return city


def dict_value(obj, field, d):
    current = obj
    current_d = d
    s = field.split('.')
    for num, y in enumerate(s):
        if current is None:
            return None
        if num < len(s) - 1:
            t = current_d.get(y, {})
            current_d[y] = t
            current_d = current_d[y]
        else:
            current_d[y] = getattr(current, y)
        current = getattr(current, y)


def shorten(text, width, **kwargs):
    text = strip_tags(text or u'')
    if len(text) < width:
        return text
    s = text.strip().split()
    res = u''
    for x in s:
        res += u' ' + unicode(x)
        if len(res) >= width:
            break

    if res >= width:
        res += u' ...'

    return res


def get_location(country_slug, region_slug, city_slug):
    location = None
    if region_slug == '-':
        location = Country.objects.get(slug=country_slug)
    elif city_slug == '-':
        country = Country.objects.get(slug=country_slug)
        location = Region.objects.get(country_id=country.id,
                                      slug=region_slug)
    else:
        country = Country.objects.get(slug=country_slug)
        region = Region.objects.get(slug=region_slug,
                                    country_id=country.id)
        location = City.objects.get(slug=city_slug,
                                    region_id=region.id,
                                    country_id=country.id)
    return Location(location)


class Location(object):
    def __init__(self, id_or_object, type_=None):
        if isinstance(id_or_object, int):
            self.id = id_or_object
            self.type_ = type_
        else:
            self.id = id_or_object.id
            self.type_ = id_or_object.__class__.__name__.lower()

    @property
    def item(self):
        if self.type_ == 'city':
            city = City.objects.get(id=self.id)
            return city
        elif self.type_ == 'region':
            region = Region.objects.get(id=self.id)
            return region
        else:
            country = Country.objects.get(id=self.id)
            return country

    @property
    def slug(self):
        if self.type_ == 'city':
            city = City.objects.get(id=self.id)
            return [str(city.country.slug), str(city.region.slug), str(city.slug)]
        elif self.type_ == 'region':
            region = Region.objects.get(id=self.id)
            return [str(region.country.slug), str(region.slug), '-']
        else:
            country = Country.objects.get(id=self.id)
            return [str(country.slug), '-', '-']

    @property
    def dest_urls(self):
        item = self.item
        if self.type_ == 'city':
            args = [item.country.slug, item.region.slug, item.slug]
        elif self.type_ == 'region':
            args = [item.country.slug, item.slug, '-']
        else:
            args = [item.slug, '-', '-']
        return {
            'destination': reverse('destination', args=args),
            'hotels': reverse('dest_hotels', args=args),
            'vacation_rentals': reverse('dest_vacation_rentals', args=args),
            'activities': reverse('dest_activities', args=args),
            'restaurants': reverse('dest_restaurants', args=args),
            'beaches': reverse('dest_beaches', args=args),
            'deals': reverse('dest_deals', args=args),
        }

    def address(self):
        if self.type_ == 'city':
            return str('%s, %s, %s' % (self.item.country.name,
                                       self.item.region.name,
                                       self.item.name))
        elif self.type_ == 'region':
            return str('%s, %s' % (self.item.country.name,
                                   self.item.name))
        return str('%s' % self.item.name)

    def as_dict(self):
        return {
            'id': self.id,
            'type': self.type_,
            'slug': self.slug,
            'address': self.address(),
        }


def get_api_url(request):
    api_url = os.environ.get('API_URL', None)
    if api_url is None:
        api_url = getattr(settings, 'API_SEARCH_URL', None)
    if api_url is None:
        http_host = request.META['HTTP_HOST']
        if 'cms' not in http_host:
            s = 'http://cms.%s/api/v1/'
        else:
            s = 'http://%s/api/v1/'
        api_url = s % http_host
    return api_url


ignore_slug_words = set([
    'a',
    'the',
    'is',
])


import re
escape_re = re.compile(r'%([0-9a-fA-F][0-9a-fA-F])')

def _unescape_http_code(match):
    code = int(match.group(1), 16)
    return chr(code)

def http_unescape(s):
    if s:
        return escape_re.sub(_unescape_http_code, s)
    else:
        return s


def slugify(s):
    part1 = http_unescape(s)
    if isinstance(part1, str):
        part1 = part1.decode('utf8')
    elif not isinstance(part1, unicode):
        part1 = unicode(part1)

    part1 = unidecode(part1)
    # part1 is now a competely safe ascii string

    part2 = ''
    for x in part1:
        x = x.lower()
        if x.isalnum():
            part2 += x
        else:
            if not part2.endswith('-'):
                part2 += '-'

    words = []
    for word in part2.split('-'):
        if word not in ignore_slug_words:
            words.append(word)

    return '-'.join(words)


_range = range(1000)

def unique_resource_slug(resource_class, s):
    orig_slug = slug = slugify(s)
    for x in _range:
        if resource_class.objects.filter(slug=slug).count() == 0:
            return slug
        slug = orig_slug + '-' + str(x+1)


def unique_slugify(obj, value, slug_field_name='slug', times_to_try=1000):
    if not value:
        return False
    slug_field = obj._meta.get_field(slug_field_name)
    slug_len = slug_field.max_length

    orig_slug = slugify(value)
    if orig_slug.startswith('-'):
        orig_slug = orig_slug[1:]
    slug = orig_slug
    if getattr(obj, slug_field_name) == slug:
        return False

    base_q = obj.__class__.objects.only('id', 'slug').exclude(id=obj.id)

    slug = _ensure_slug_len(slug, slug_len)
    q = base_q.filter(slug=slug)
    if q.count() == 0:
        obj.slug = slug
        return True

    if obj.id is not None:
        slug = slug + '-' + str(obj.id)

    slug = _ensure_slug_len(slug, slug_len)
    q = base_q.filter(slug=slug)
    if q.count() == 0:
        obj.slug = slug
        return True

    for x in xrange(times_to_try):
        if q.count() == 0:
            obj.slug = slug
            return True

        slug = orig_slug + '-' + str(x+1)
        slug = _ensure_slug_len(slug, slug_len)

        q = base_q.filter(slug=slug)

    raise ValueError('Was not able to find a unique slug for %s' % str(obj))

def _ensure_slug_len(slug, slug_len):
    if len(slug) > slug_len:
        slug = slug[:slug_len-(len(str(x) + 1))]
        slug = _slug_strip(slug, '-')

    return slug

def _slug_strip(value, separator='-'):
    """
    Cleans up a slug by removing slug separator characters that occur at the
    beginning or end of a slug.

    If an alternate separator is used, it will also replace any instances of
    the default '-' separator with the new separator.
    """
    separator = separator or ''
    if separator == '-' or not separator:
        re_sep = '-'
    else:
        re_sep = '(?:-|%s)' % re.escape(separator)
    # Remove multiple instances and if an alternate separator is provided,
    # replace the default '-' separator.
    if separator != re_sep:
        value = re.sub('%s+' % re_sep, separator, value)
    # Remove separator from the beginning and end of the slug.
    if separator:
        if separator != '-':
            re_sep = re.escape(separator)
        value = re.sub(r'^%s+|%s+$' % (re_sep, re_sep), '', value)
    return value


class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return u''.join(self.fed)


def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()




def distance_on_unit_sphere(lat1, long1, lat2, long2):
    lat1 = float(lat1)
    long1 = float(long1)
    lat2 = float(lat2)
    long2 = float(long2)

    # Convert latitude and longitude to
    # spherical coordinates in radians.
    degrees_to_radians = math.pi/180.0

    # phi = 90 - latitude
    phi1 = (90.0 - lat1)*degrees_to_radians
    phi2 = (90.0 - lat2)*degrees_to_radians

    # theta = longitude
    theta1 = long1*degrees_to_radians
    theta2 = long2*degrees_to_radians

    # Compute spherical distance from spherical coordinates.

    # For two locations in spherical coordinates
    # (1, theta, phi) and (1, theta, phi)
    # cosine( arc length ) =
    #    sin phi sin phi' cos(theta-theta') + cos phi cos phi'
    # distance = rho * arc length
    try:
        if lat1 != lat2 and long1 != long2:
            cos = (math.sin(phi1) * math.sin(phi2) * math.cos(theta1 - theta2) +
                   math.cos(phi1)*math.cos(phi2))
            arc = math.acos(cos)
        else:
            # values being the same will cause a math domain error
            arc = None
    except ValueError:
        arc = None
    # Remember to multiply arc by the radius of the earth
    # in your favorite set of units to get length.
    return arc


def distance_in_miles(lat1, long1, lat2, long2):
    distance = distance_on_unit_sphere(lat1, long1, lat2, long2)
    if distance is not None:
        return distance * 3960
    else:
        return None
