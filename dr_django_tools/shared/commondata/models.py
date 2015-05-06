import os
from django.db import models

try:
    from cities import models as cities_models
except ImportError:
    pass

from lazy import lazy
from PIL import Image
from django.conf import settings

from django.contrib.gis.db import models as gis_models
from dr_django_tools.shared.commondata.utils import (image_path,
                                             unique_slugify,
                                             update_image,
                                             THUMBNAIL_DIMS,
                                             IMAGE_TYPE_GENERAL,
                                             IMAGE_TYPE_VENDOR_THUMB,
                                             IMAGE_TYPE_PHOTO_THUMB,
                                             IMAGE_TYPE_EXTENDED,
                                             IMAGE_TYPE_SELECTED_THUMB)
from dr_django_tools.shared.commondata.image_utils import resize_and_crop

LOCATION_TYPES = (
    ('city', 'City'),
    ('region', 'Region'),
    ('country', 'Country'),
)
DEFAULT_LOCATION_TYPE = LOCATION_TYPES[0][0]

slug_templates = settings.SLUG_TEMPLATES
image_slug_templates =  settings.IMAGE_SLUG_TEMPLATES
resource_slugbase = settings.RESOURCE_SLUG_BASE


class LocationAware(models.Model):
    location_id = models.IntegerField()
    location_type = models.CharField(max_length=10,
                                     choices=LOCATION_TYPES,
                                     default=DEFAULT_LOCATION_TYPE)

    @property
    def location(self):
        if self.location_type == 'country':
            model_class = cities_models.Country
        elif self.location_type == 'region':
            model_class = cities_models.Region
        else:
            model_class = cities_models.City

        return model_class.objects.get(id=self.location_id)

    class Meta:
        abstract = True


class SelectedPhotoAware(object):

    @lazy
    def image_class(self):
        for pkg in settings.IMAGE_MODELS:
            try:
                module = __import__(pkg, globals(), locals(),[self.__class__.__name__+'Image'])
                if hasattr(module, self.__class__.__name__+'Image'):
                    return getattr(module, self.__class__.__name__+'Image')
            except Exception:
                pass

    @property
    def selected_photo(self):
        for image_type in (IMAGE_TYPE_SELECTED_THUMB,
                           IMAGE_TYPE_GENERAL,
                           IMAGE_TYPE_PHOTO_THUMB,
                           IMAGE_TYPE_VENDOR_THUMB):
            q = self.image_class.objects.filter(
                resource=self, image_type=image_type).order_by('order')
            if q.count() > 0:
                return q.all()[0]

        return None

    @property
    def selected_photo_path(self):
        if not self.selected_photo:
            return ''
        return '%s.jpg' % self.selected_photo.slug

    @property
    def selected_photo_alt(self):
        if not self.selected_photo:
            return None
        return self.selected_photo.alt

    @property
    def listing_photo(self):
        return self.selected_photo

    @property
    def listing_photo_path(self):
        photo = self.listing_photo
        return '%s.jpg' % photo.slug if photo is not None else ''

    @property
    def listing_photo_alt(self):
        photo = self.listing_photo
        return photo.alt if photo is not None else ''

    @property
    def profile_photo(self):
        return self.selected_photo

    @property
    def profile_photo_path(self):
        photo = self.profile_photo
        return '%s.jpg' % photo.slug if photo is not None else ''

    @property
    def profile_photo_alt(self):
        photo = self.profile_photo
        return photo.alt if photo is not None else ''


class MetaAware(models.Model):
    class Meta:
        abstract = True

    meta_title = models.CharField(max_length=125, blank=True, null=True)
    meta_keywords = models.TextField(blank=True, null=True)
    meta_description = models.TextField(blank=True, null=True)


class GISMetaAware(gis_models.Model):
    class Meta:
        abstract = True

    meta_title = models.CharField(max_length=100, blank=True, null=True)
    meta_keywords = models.CharField(max_length=200, blank=True, null=True)
    meta_description = models.TextField(blank=True, null=True)

def save_resource(obj):
    if not obj.slug:
        slugbase = resource_slugbase(obj)
        unique_slugify(obj, slugbase)


class Resource(MetaAware, SelectedPhotoAware):
    class Meta:
        abstract = True
    slug = models.CharField(max_length=200, null=True, blank=True)

    def save(self):
        save_resource(self)
        super(Resource, self).save()

class Slug(models.Model):
    class Meta:
        abstract = True
    slug = models.CharField(max_length=200, null=True, blank=True)

    def save(self):
        save_resource(self)
        super(Slug, self).save()

IMAGE_TYPES = [
    # standard photo provided by vendor
    (IMAGE_TYPE_GENERAL, 'general'),

    # provided by vendor
    (IMAGE_TYPE_VENDOR_THUMB, 'vendor_thumbnail'),

    # generated by us for every full size photo imported
    (IMAGE_TYPE_PHOTO_THUMB, 'photo_thumbnail'),

    # thumbnail probably generated by us
    (IMAGE_TYPE_SELECTED_THUMB, 'selected_thumbnail'),

    # thumbnail probably generated by us
    (IMAGE_TYPE_EXTENDED, 'extended'),
]


class Resizeable(object):
    def __init__(self, parent):
        self.parent = parent

    def __getitem__(self, k):
        '''Supports retrieving an image with a key of the following formats:
           - '100x200'
           - (100, 200)
        '''

        if isinstance(k, basestring):
            width, height = k.strip().lower().split('x')
            width = int(width.strip())
            height = int(height.strip())
        else:
            width, height = k

        q = self.parent.__class__.objects.filter(
            parent=self.parent,
            width=width,
            height=height,
        )
        if q.count() > 0:
            return q[0]

        return self._generate(width, height)

    def _generate(self, width, height):
        parent = self.parent
        new_image = parent.__class__(resource=parent.resource,
                                     source=parent.source,
                                     parent=parent,
                                     image_type=IMAGE_TYPE_PHOTO_THUMB,
                                     width=width,
                                     height=height)
        new_image.save()
        resource_type = parent.resource.__class__.__name__.lower()
        source = parent.file_path
        target = image_path(resource_type, new_image.id)

        d = os.path.dirname(target)
        if not os.path.exists(d):
            os.makedirs(d)

        resize_and_crop(source, target, (width, height))
        new_image.save()

        return new_image


def update_binary(image, url, force=False, generate_thumbnail=False):
    resource_type = image.resource.__class__.__name__.lower()
    if not os.path.exists(image.file_path) or force:
        update_image(resource_type, image, url)
    if generate_thumbnail:
        image.ensure_thumbnail()


def file_path(image):
    source = image_path(type_=image.resource.__class__.__name__.lower(), id=image.id)
    return source


def ensure_thumbnail(image):
    if image.thumbnail is not None:
        return

    new_image = image.__class__()
    new_image.resource = image.resource
    new_image.image_type = IMAGE_TYPE_PHOTO_THUMB
    new_image.width = THUMBNAIL_DIMS[0]
    new_image.height = THUMBNAIL_DIMS[1]
    new_image.source = image.source

    unique_slugify(new_image, image.slug)
    new_image.save()
    resource_type = image.resource.__class__.__name__.lower()
    source = image.file_path
    target = image_path(resource_type, new_image.id)

    d = os.path.dirname(target)
    if not os.path.exists(d):
        os.makedirs(d)

    resize_and_crop(source,
                    target,
                    THUMBNAIL_DIMS)


class BaseImage(models.Model):

    class Meta:
        abstract = True

    slug = models.CharField(max_length=200, null=True, blank=True)
    order = models.IntegerField(null=True, blank=True, default=1000)

    @lazy
    def resized(self):
        return Resizeable(self)

    @property
    def alt(self):
        alt = u''
        try:
            if hasattr(self,'resource') and hasattr(self.resource,'name'):
                alt += self.resource.name
            else:
                if hasattr(self,'resource') and hasattr(self.resource,'destination') and self.resource.destination is not None:
                    alt += self.resource.name + ', ' + self.resource.destination.name

            if hasattr(self,'description'):
                alt += ' - ' + self.description
        except Exception as e:
            pass

        return alt or ''

    @property
    def thumbnail(self):
        try:
            image = self.__class__.objects.get(
                resource=self.resource,
                source=self.source,
                image_type=IMAGE_TYPE_PHOTO_THUMB)
            return image
        except Exception as e:
            return None

    @property
    def thumbnail_path(self):
        if self.thumbnail is None:
            return None
        return '%s.jpg' % self.thumbnail.slug

    def ensure_thumbnail(self):
        ensure_thumbnail(self)

    @property
    def binary_exists(self):
        return os.path.exists(self.file_path)

    @property
    def file_path(self):
        return file_path(self)

    def update_binary(self, url, force=False, generate_thumbnail=False):
        update_binary(self, url, force, generate_thumbnail)

    def remove(self):
        if self.binary_exists:
            os.remove(self.file_path)
        self.delete()

    def save(self):
        super(BaseImage, self).save()
        setup_image_slug(self)
        setup_image_dims(self)
        super(BaseImage, self).save()


def setup_image_dims(image):
    if image.binary_exists:
        im = Image.open(image.file_path)
        image.width, image.height = im.size


def setup_image_slug(image):
    if not image.slug:
        rname = image.__class__.__name__
        rname = rname[:-5]
        templ = image_slug_templates[rname]
        unique_slugify(image, templ % {
            'resource_name': getattr(image.resource, 'name', ''),
            'image_description': getattr(image, 'description', '') or '',
        })
