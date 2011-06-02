#
# formats.py
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

from deluge.common import fsize, fpcnt, fspeed as _fspeed1, fpeer, ftime, fdate


def fqueue(queue):
    return "" if queue < 0 else str(queue + 1)

def fratio(ratio):
    if ratio < 0:
        return u"\u221E" # infinity symbol
    return "%.3f" % ratio

def fspeed(speed, limit_kib= -1):
    speed = _fspeed1(speed)
    if limit_kib > -1:
        return "%s (%s %s)" % (speed, limit_kib, _("KiB/s"))
    return speed

def fsize2(size, second_size=None):
    if second_size:
        return "%s (%s)" % (fsize(size), fsize(second_size))
    return fsize(size)

def fpieces(pieces, length):
    return "%s (%s)" % (pieces, fsize(length))
