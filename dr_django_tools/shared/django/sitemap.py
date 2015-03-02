from xml.etree import ElementTree as etree
from django.http import Http404, HttpResponse

class SiteMap(object):
    top_type = 'urlset'
    sub_type = 'url'
    change_freq = 'monthly'

    def __init__(self, initial=None):
        if initial:
            self._entries = list(initial)
        else:
            self._entries = []

        self._last_modified = []

    def add(self, url):
        self._entries.append(url)

    def render(self, request):
        root = etree.Element(self.top_type)
        root.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
        for k, entry in enumerate(self._entries):
            url_el = etree.SubElement(root, self.sub_type)
            loc_el = etree.SubElement(url_el, 'loc')
            loc_el.text = request.build_absolute_uri(entry)

            try:
                if self._last_modified[k]:
                    loc_el = etree.SubElement(url_el, 'lastmod')
                    loc_el.text = self._last_modified[k].strftime('%Y-%m-%d')
            except IndexError:
                pass
            if self.sub_type == 'url':
                loc_el = etree.SubElement(url_el, 'changefreq')
                loc_el.text = self.change_freq

        response = HttpResponse(etree.tostring(root), 'text/xml')
        return response

class Columnizer(object):
    def __init__(self, results):
        self.results = results

    def __getattr__(self, k):
        if k in dir(Columnizer):
            return object.__getattr__(self, k)
        collen = int(k)
        cols = []
        row = []
        multiple = int(self.count / collen)
        if self.count % collen > 0:
            multiple += 1
        for (x, res) in enumerate(self.results):
            if x % multiple == 0:
                row = []
                cols.append(row)
            row.append(res)
        return cols

    @property
    def count(self):
        return len(self.results)

class SiteMapIndex(SiteMap):
    top_type = 'sitemapindex'
    sub_type = 'sitemap'