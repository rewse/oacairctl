#!/usr/bin/python
#coding: UTF-8
###############################################################################
# @(#) Oracle Aoyama Center Air-Conditioner Controller
#
# Start or stop the air-coditioners at Oracle Aoyama Center by CUI.
# Only Oracle employees can use this program.
#
# Copyright (c) 2012 Tats Shibata
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
###############################################################################
# {{{ const

__version__ = "1.0.0"

LOGIN_URL = "baweb/CMN/asp/topmenu_frame.asp"
CONTROL_URL = "baweb/sum/asp/hattei.asp"
STATUS_URL = "baweb/sum/asp/summry_rst.asp"

#}}}
# {{{ import

import cookielib
import getopt
import random
import re
import sys
import time
import traceback
import urllib
import urllib2

# }}}
# {{{ Option

class Option(object):
  def __init__(self, opts, args):
    self._set_opts(opts)
    self._set_args(args)
    self._check_none()

  # getter / setter

  def get_sleep_sec(self):
    return self.__sleep_sec

  def set_sleep_sec(self, sleep_sec):
    try:
      self.__sleep_sec = int(sleep_sec)
    except ValueError:
      print >>sys.stderr, \
        "[ERROR] SLEEP must be a digit [SLEEP=%s]" % (sleep_sec)
      usage()
      sys.exit(1)

  sleep_sec = property(get_sleep_sec, set_sleep_sec)

  def get_command(self):
    return self.__command

  def set_command(self, command):
    if command in ("start", "stop", "status"):
      self.__command = command
    else:
      print >>sys.stderr, \
        "[ERROR] COMMAND must be start or stop [COMMAND=%s]" % (command)
      usage()
      sys.exit(1)

  command = property(get_command, set_command)

  def get_positions(self):
    return self.__positions

  def set_positions(self, positions):
    try:
      int_positions = [int(position) for position in positions]
    except ValueError:
      print >>sys.stderr, \
        "[ERROR] All POSITION_NO must be digits [POSITION_NO=%s]" % (position)
      usage()
      sys.exit(1)

    self.__positions = int_positions

  positions = property(get_positions, set_positions)

  def _set_opts(self, opts):
    for o, a in opts:
      if o in ("-s", "--sleep"):
        self.set_sleep_sec(a)
      if o in ("-x", "--proxy"):
        self.proxy = a
      if o in ("-V", "--version"):
        version()
        sys.exit(1)
      if o in ("-h", "--host"):
        self.host = a
      if o in ("-u", "--user"):
        self.user = a
      if o in ("-p", "--password"):
        self.password = a

  def _set_args(self, args):
    # do not use "except IndexError" because args[1:] never raises it
    if len(args) > 1:
      self.set_command(args[0])
      self.set_positions(args[1:])
    else:
      print >>sys.stderr, "[ERROR] Arguments are not enough"
      usage()
      sys.exit(1)

  def _check_none(self):
    DEFAULT_SLEEP_SEC = 0

    try:
      self.host
    except AttributeError:
      print >>sys.stderr, "[ERROR] HOST is required"
      usage()
      sys.exit(1)

    try:
      self.user
    except AttributeError:
      print >>sys.stderr, "[ERROR] USER is required"
      usage()
      sys.exit(1)

    try:
      self.password
    except AttributeError:
      print >>sys.stderr, "[ERROR] PASSWORD is required"
      usage()
      sys.exit(1)

    try:
      self.proxy
    except AttributeError:
      self.proxy = None

    try:
      self.sleep_sec
    except AttributeError:
      self.__sleep_sec = DEFAULT_SLEEP_SEC

# }}}
# {{{ usage()

def usage():
  print >>sys.stderr, """
[USAGE] oacairctl [-sxV] -h <HOST> -u <USER> -p <PASSWORD> <COMMAND> <POSITION_ID> [<POSITION_ID> ... ]

COMMAND:
  start            Start the air-conditioner at <POSITION_ID>
  stop             Stop the air-conditioner at <POSITION_ID>
  status           Get status of the air-conditioner at <POSITION_ID>

POSITION_ID:
  This is a unique number. You can get it by the below

  1. Get the URL of the air-conditioner site from "Facility: Guide/FAQ"
  2. Login the site by graphical web browser like Firefox.
  3. Choose your floor
  4. Get ready to capture HTTP request by such as Live HTTP Headers add-on
  5. Choose your duct
  6. kcode in GET request is a POSITION_ID

  List separated by space when you control multiple ducts at the same time

OPTION:
  -h, --host        Host of URL. Get it from "Facility: Guide/FAQ"
                    Do not include any protoctol, path or files
                    OK example) www.oracle.com   192.168.0.1
                    NG example) www.oracle.com/jp/   http://192.168.0.1/foo.php
  -u, --user        Username. Get it from "Facility: Guide/FAQ"
  -p, --password    Password. Get it from "Facility: Guide/FAQ"
  -s, --sleep       Set maximum sleep seconds. This program sleeps in random
                    soconds between 0 and this value before start due to
                    fluctuation.
                    The default is 0. Start immediately when the value is 0
  -x, --proxy       Proxy URL
                    OK exmaple) http://proxy.oracle.com:80/
  -V, --version     Output version information and exit

RETURN CODE:
  0                 Success
  1                 Error but you can fix yourself
  2                 Critical Error
 -1                 Unexpected Error. File a bug
"""

# }}}
# {{{ version()

def version():
  print """Oracle Aoyama Center Air-Conditioner Controller %s
""" % (__version__)

# }}}
# {{{ valid_opt()

def valid_opt(argv):
  try:
    opts, args = getopt.gnu_getopt(
      argv[1:],
      "s:x:Vh:u:p:",
      ["sleep=", "proxy=", "version", "host=", "user=", "password="]
    )
  except getopt.GetoptError:
    print >>sys.stderr, "[ERROR] Unknown option"
    usage()
    sys.exit(1)

  return Option(opts, args)

# }}}
# {{{ login()

def login(host, user, password, proxy):
  print "Logging in..."

  opener = urllib2.build_opener(
    urllib2.HTTPCookieProcessor(cookielib.CookieJar())
  )

  if proxy is not None:
    opener.add_handler(urllib2.ProxyHandler({'http': proxy}))

  try:
    res = opener.open(
      "http://%s/%s" % (host, LOGIN_URL),
      urllib.urlencode({
        "language": "ja",
        "UserName": user,
        "UserPass": password
      })
    )
  except urllib2.URLError:
    print >>sys.stderr, "[ERROR] URL request error [URL=%s]" % res.geturl()
    sys.exit(1)

  res_body = res.read().decode("shift_jis", "replace")

  # have to look for the body due to always 200 returned
  if res_body.find(u"フレーム機能をサポートしていないブラウザ") != -1:
    print "Logged in"
  else:
    print >>sys.stderr, "[ERROR] Login was failed"
    sys.exit(1)

  return opener

# }}}
# {{{ sleep()

def sleep(max_sleep_sec):
  sleep_sec = random.randint(0, max_sleep_sec)

  print "Sleeping %d seconds..." % sleep_sec
  time.sleep(sleep_sec)

# }}}
# {{{ control()

def control(opener, host, command, positions):
  command_no = {"start": 1, "stop": 0}[command]

  if command_no is None:
    raise RuntimeError("[ERROR] Unexpected error [POS=1,COMMAND=%s]" % (opt.command))
    sys.exit(-1)

  for position in positions:
    print "Requesting to %s %s..." % (command, position)

    try:
      res = opener.open(
        "http://%s/%s?%s" % (host, CONTROL_URL, urllib.urlencode({
          "optStatus": command_no,
          "kcode": position,
          "hidHattei": "NONE_NUL"
        }))
      )
    except urllib2.URLError:
      print >>sys.stderr, "[ERROR] URL request error [URL=%s]" % res.geturl()
      sys.exit(1)

    res_body = res.read().decode("shift_jis", "replace")

    # have to look for the body due to always 200 returned
    if res_body.find(u"機器を選択して下さい") != -1:
      print "The request was successful"
    else:
      print >>sys.stderr, "[WARNING] The request was failed"

# }}}
# {{{ status()

def status(opener, host, positions):
  for position in positions:
    print "Requesting status of %s..." % position

    position = str(position)

    if len(position) == 5:
      floor_id = "500%s" % position[0]
    elif len(position) == 6:
      floor_id = "50%s" % position[:2]
    else:
      print >>sys.stderr, "[ERROR] POSITION_ID is not found [POSITION_ID=%s]" % position
      sys.exit(1)

    try:
      res = opener.open(
        "http://%s/%s?%s" % (host, STATUS_URL, urllib.urlencode({
          "id": floor_id
        }))
      )
    except urllib2.URLError:
      print >>sys.stderr, "[ERROR] URL request error [URL=%s]" % res.geturl()
      sys.exit(1)

    if _get_status_flag(position, res.read().decode("shift_jis", "replace")):
      print "%s is ON" % position
    else:
      print "%s is OFF" % position

# }}}
# {{{ _get_status_flag()

def _get_status_flag(position, res_body):
  status_no = None
  pat = re.compile(r'dchcol,\d,%s.+DDP:\d:(\d+)' % position)

  for match in pat.finditer(res_body):
    status_no = int(match.group(1))

  if status_no is None:
    print >>sys.stderr, "[ERROR] POSITION_ID is not found [POSITION_ID=%s]" % position
    sys.exit(1)

  return status_no in (4128, 10272, 15392, 20512, 36896, 53280)

# }}}
# {{{ main()

def main():
  opt = valid_opt(sys.argv)

  if opt.command in ("start", "stop"):
    version()
    opener = login(opt.host, opt.user, opt.password, opt.proxy)
    sleep(opt.sleep_sec)
    control(opener, opt.host, opt.command, opt.positions)
  elif opt.command in ("status"):
    version()
    opener = login(opt.host, opt.user, opt.password, opt.proxy)
    status(opener, opt.host, opt.positions)
  else:
    raise RuntimeError("[ERROR] Unexpected error [POS=0,COMMAND=%s]" % (opt.command))
    sys.exit(-1)

if __name__ == "__main__":
  main()
