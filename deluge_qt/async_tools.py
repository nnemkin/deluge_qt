
import sys
import functools
import logging

import sip
from twisted.internet import defer

log = logging.getLogger(__name__)


def inlineCallbacks(func):
    """Enhanced version of inlineCallbacks."""

    def g_proxy(self, *args, **kwargs):
        g = func(self, *args, **kwargs)
        result = None
        while not sip.isdeleted(self):
            result = g.send(result)
            try:
                result = yield result
            except (GeneratorExit, StopIteration):
                break
            except Exception:
                if not sip.isdeleted(self):
                    g.throw(*sys.exc_info()) # NB: can raise anything and we'll propagate it
                else:
                    log.debug("Ignored exception on deleted object", exc_info=True)
        g.close()

    return defer.inlineCallbacks(functools.wraps(func)(g_proxy))
