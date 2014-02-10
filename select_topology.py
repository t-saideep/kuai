#!/usr/bin/env python

import sys

if len(sys.argv) != 3:
    print >>sys.stderr, "Need configuration directory and a topology number"
    sys.exit(1)

import subprocess

config_dir = sys.argv[1]
topology_num = sys.argv[2]

subprocess.check_call(['cp', "%s/topology.%s" % (config_dir, topology_num), "%s/topology" % config_dir])
print "Selected %s" % topology_num