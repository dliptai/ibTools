#!/usr/bin/env python
# this bobMonitor config file must contain only legal python code!!

# to link to your site's regular web pages
siteName = "OzStar"
siteURL = "https://supercomputing.swin.edu.au"

# name of the cookie for this bobMonitor instance. will be prefixed by 'bobMon-'
cookieSuffix = "farnarkle"

# paths in web space
gifDir = "/bobMon/gifs/"
pieURL = "/bobMon/pies/"
bobDataCmdURL = "/cgi-bin/catBobData"
# ganglia-web needs this ->
# bobDataCmdURL = '/bobMon/api/catBobData'

# paths in file space
pbsPath = "/opt/torque/bin"
mauiPath = "/opt/moab/bin"
piePath = "/var/www/html/bobMon/pies/"
dataPath = "/var/spool/bobMon/"
trimImage = "/usr/sbin/trimImage"

# known values: torque, anupbs, slurm
batchType = "slurm"

# ganglia config
# gather and merge data from all these gmonds
# these gmond's can provide the same data (gmonds in redundant config) or different data (eg. compute ganglia and storage ganglia)
#
# host, port, url
# url can be relative to this website or absolute. %h is expanded to the hostname
gmonds = [["transom1", "8649", "/ganglia/?c=farnarkle&metric_group=NOGROUPS&h=%h"]]

# non-standard data in ganglia that we want to harvest and use
# NOTE: there needs to be server code in bobMon.py to insert these into the xml
#       and client side code in bobMon.js to display them.
#       so this line isn't all that is required to enable these features
extraGangliaMetrics = [
    "ib_bytes_in",
    "ib_bytes_out",
    "ib_pkts_in",
    "ib_pkts_out",
    "farnarkle_fred_mds_ops",
    "farnarkle_fred_oss_ops",
    "farnarkle_fred_read_bytes",
    "farnarkle_fred_write_bytes",
    "farnarkle_apps_mds_ops",
    "farnarkle_apps_oss_ops",
    "farnarkle_apps_read_bytes",
    "farnarkle_apps_write_bytes",
    "farnarkle_home_mds_ops",
    "farnarkle_home_oss_ops",
    "farnarkle_home_read_bytes",
    "farnarkle_home_write_bytes",
    "farnarkle_images_mds_ops",
    "farnarkle_images_oss_ops",
    "farnarkle_images_read_bytes",
    "farnarkle_images_write_bytes",
    "gpu0_util",
    "gpu1_util",
    "gpu2_util",
    "gpu3_util",
    "gpu4_util",
    "gpu5_util",
    "gpu6_util",
    "cpu1_temp",
    "cpu2_temp",
    "ambient_temp",
    "chassis_temp",
    "rear_temp",
    "front_temp",  # temperatures
    "node_power",
    "cmm_power_in",
    "fan_rms",  # node and cmm input kw, cmm fans
]

# map and scale ganglia metrics to byte/s in/out and packets/s in/out
metricMap = [
    "network",
    [
        "ib_bytes_in",
        ["ib_bytes_in", 1],
        "ib_bytes_out",
        ["ib_bytes_out", 1],
        "ib_packets_in",
        ["ib_pkts_in", 1],
        "ib_packets_out",
        ["ib_pkts_out", 1],
    ],
]

# cluster config. all nodes need to be listed. the naming format is
# eg.
#  y[1-1492]              -> y1 y2 ... y1492
#  x[003-007,100-200]-ib  -> x003-ib x004-ib ... x007-ib x100-ib x101-ib ... x200-ib
computeNodes = [
    "john[1-110]",
    "bryan[1-8]",
    "gina[1-4]",
    "gstar[011-059,101-105,201-204]",
    "sstar[011-032,101-167,301-301]",
    "clarke[1-10]",
]
headNodes = [
    "farnarkle[1-2]",
    "sstar",
    "gstar",
    "transom[1-2]",
    "phlange",
    "data-mover[01-04]",
    "hpc-mgmt",
    "tapeserv01",
]
ioNodes = [
    "lnet[01-10]",
    "warble[1-2]",
    "arkle[1-10]",
    "umlaut[1-4]",
    "metadata101",
    "object[101-102]",
]

# time to sleep between stats gathering from ganglia, pbs etc.
sleepTime = 10  # time in seconds

# jobs stats are ignored for several iterations when a job starts and also when
# it comes back from being suspended because ganglia has a ~30s+ lag in it
# and we don't want to record leftover node stats from the previous job
ignoreStatsLoops = 6  # in units of sleepTime. eg. sleepTime * ignoreStatsLoops ~= 60s

# this hasn't been tested for a long time - might be broken:
showRackLoads = 0

# temperature display min/max for cpu
cpuMinTemp = 20.0
cpuMaxTemp = 100.0

# temperature display min/max for node
mb0MinTemp = 30.0  # rear blade
mb0MaxTemp = 70.0
mb1MinTemp = 20.0  # front blade
mb1MaxTemp = 40.0

ambientWarn = 45.0  # 35 is typical limit, but ambient sensors are often way off

# for the temperature display:
rackTempOrder = "up"  #   up == low number node at the bottom of display
# down == low number node at the top of display

# temperature font size
tempFontSize = -2

# format here is [ 'name', 'type' ] where allowable types are 'head' and 'node'
# or [ '' ] if the element is to be left blank
# the name 'head' and 'i/o' are special tags that the server knows about
# and need to be kept? additional 'head' names are allowed
specialRows = [
    [
        ["login", "head"],
        ["farnarkle[1-2]", "node"],
        ["sstar", "node"],
        ["gstar", "node"],
        ["infra- structure", "head"],
        ["transom[1-2]", "node"],
        ["hpc-mgmt", "node"],
        ["dm", "head"],
        ["data-mover[01-04]", "node"],
        ["misc", "head"],
        ["phlange", "node"],
        ["tapeserv01", "node"],
    ],
    [
        ["router", "head"],
        ["lnet[01-10]", "node"],
    ],
    [
        ["mds", "head"],
        ["warble[1-2]", "node"],
        ["oss", "head"],
        ["arkle[1-10]", "node"],
        ["umlaut[1-4]", "node"],
        ["mds", "head"],
        ["metadata101", "node"],
        ["oss", "head"],
        ["object[101-102]", "node"],
    ],
]

# how nodes are layed out in the racks - used for the rack temperature display
# the 'fe' column is where all non-backend nodes will be placed
# NOTE: number of nodes here needs to add up 'numNodes'
#   format is number of nodes in rack or 'fe', then type
#     where type is 'pizza' or  ['blade',bladesPerShelf,nodesPerBlade]
# ozstar is 18 nodes/rack
racks = [
    [22, "pizza"],
    [22, "pizza"],
    [22, "pizza"],
    [22, "pizza"],
    [22, "pizza"],
    [20, "pizza"],
    [25, "pizza"],
    [25, "pizza"],
    [25, "pizza"],
    [25, "pizza"],
    [25, "pizza"],
    [25, "pizza"],
    [10, "pizza"],
    ["fe", "pizza"],
]

# name the blade shelves eg. cmm1, cmm2, ...
# number of shelves should add up to the number described in racks[]
shelves = []

shelfFanMinSpeed = 3000
shelfFanMaxSpeed = 6000
shelfMinPower = 2000
shelfMaxPower = 9000

# used in the per-job kW calculations.
# set a multiplier on the Watts reported by each node to reflect the real
# (wall) power being used rather than the power measured at each node. eg.
#   1.0  - the power for nodes is unmodified from that in ganglia
#   1.15 - modify the power reported by nodes in blades to account for
#          losses in the shelf/rack power supplies
nodeWattsMultiplier = 1.13
