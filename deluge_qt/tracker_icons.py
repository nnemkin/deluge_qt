#
# tracker_icons.py
#
# Copyright (C) 2010 Nikita Nemkin <nikita@nemkin.ru>
#
# This file is part of Deluge.
#
# Deluge is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Deluge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Deluge. If not, see <http://www.gnu.org/licenses/>.
#
#    In addition, as a special exception, the copyright holders give
#    permission to link the code of portions of this program with the OpenSSL
#    library.
#    You must obey the GNU General Public License in all respects for all of
#    the code used other than OpenSSL. If you modify file(s) with this
#    exception, you may extend this exception to your version of the file(s),
#    but you are not obligated to do so. If you do not wish to do so, delete
#    this exception statement from your version. If you delete this exception
#    statement from all source files in the program, then also delete it here.
#

import os
import logging
import urlparse
import HTMLParser

from twisted.python import failure
from twisted.internet import reactor, defer
from twisted.web import client

from deluge import configmanager, component, httpdownloader

log = logging.getLogger(__name__)

ICON_EXTENSIONS = frozenset(["gif", "jpg", "jpeg", "png", "ico"])


class _FaviconResult(Exception):

    def __init__(self, href=None):
        self.href = href


class _FaviconLinkExtractor(HTMLParser.HTMLParser):

    def handle_starttag(self, tag, attrs):
        if tag == 'link':
            attrs = dict(attrs)
            try:
                if 'icon' in attrs['rel'].lower() and os.path.splitext(attrs['href'])[1] in ICON_EXTENSIONS:
                    raise _FaviconResult(attrs['href'])
            except KeyError:
                pass
        elif tag in ('body', 'p', 'div', 'a', 'table'): # content started, favicon link not found 
            raise _FaviconResult()


class _FaviconClient(client.HTTPClientFactory):

    class protocol(client.HTTPPageDownloader):

        def handleResponsePart(self, data):
            client.HTTPPageDownloader.handleResponsePart(self, data)
            if self.factory.parser_finished:
                self.quietLoss = True # do not call pageEnd
                self.transport.loseConnection()

    def __init__(self, url, **kwargs):
        client.HTTPClientFactory.__init__(self, url, **kwargs)
        self.parser_finished = False

    def execute(self):
        if self.scheme == "https":
            from twisted.internet import ssl
            reactor.connectSSL(self.host, self.port, self, ssl.ClientContextFactory())
        else:
            reactor.connectTCP(self.host, self.port, self)
        return self.deferred

    def pageStart(self, partialContent):
        self.parser = _FaviconLinkExtractor()

    def pagePart(self, data):
        try:
            self.parser.feed(data)
        except _FaviconResult, e:
            self.parser_finished = True
            self.deferred.callback(urlparse.urljoin(self.url, e.href) if e.href else None)
        except HTMLParser.HTMLParseError:
            self.parser_finished = True
            self.deferred.errback(failure.Failure())

    def pageEnd(self):
        if not self.parser_finished: # happens when the page is valid but (almost) empty
            self.parser_finished = True
            self.deferred.callback(None)

    def noPage(self, reason):
        pass


class TrackerIcons(component.Component):

    def __init__(self):
        super(TrackerIcons, self).__init__("TrackerIcons")

        self.image_dir = os.path.join(configmanager.get_config_dir(), "icons")
        if not os.path.exists(self.image_dir):
            os.mkdir(self.image_dir)

        self.images = {}
        for filename in os.listdir(self.image_dir):
            host, ext = os.path.splitext(filename)
            if ext in ICON_EXTENSIONS:
                self.images[host] = os.path.join(self.image_dir, filename)

        self._waiting = {}

    @defer.inlineCallbacks
    def _get_filename(self, host):
        candidate_urls = []
        try:
            url = yield _FaviconClient("http://%s/" % host).execute()
            if url:
                candidate_urls.append(url)
        except Exception:
            log.debug("", exc_info=True)

        candidate_urls.append("http://%s/favicon.ico" % host)

        for url in candidate_urls:
            filename = os.path.join(self.image_dir, host + os.path.splitext(url)[1])
            try:
                yield httpdownloader.download_file(url, filename, force_filename=True)
            except Exception:
                log.debug("", exc_info=True)
            else:
                break
        else:
            filename = None

        self.images[host] = filename
        for d in self._waiting[host]:
            d.callback(filename)
        del self._waiting[host]

    def get_filename(self, host):
        return defer.succeed(None)

        host = host.lower()
        try:
            return defer.succeed(self.images[host])
        except KeyError:
            d = defer.Deferred()
            if host not in self._waiting:
                self._waiting[host] = [d]
                self._get_filename(host)
            else:
                self._waiting[host].append(d)
            return d
