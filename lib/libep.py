import sys
from datetime import datetime


def log_error(s):
    sys.stderr.write(str(datetime.now()) + ': ' + str(s) + "\n")
    sys.stderr.flush()


def log_debug(s):
    log_info("debug %s" % s)


def log_info(s):
    sys.stdout.write(str(datetime.now()) + ': ' + str(s) + "\n")
    sys.stdout.flush()


def log_fatal(s):
    log_error("fatal %s" % (s))
