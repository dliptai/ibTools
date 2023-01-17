#!/usr/bin/env python

# (c) Robin Humble 2010-2012
# licensed under the GPL v3

# get IB network stats from IB hardware and spoof them into ganglia.
# this is centralised because then no daemon needs to run on compute
# nodes.
#
# with --host aquires data from host HCA's (requires 64bit stats on hosts - so connectx fw >= 2.7.0)
# with --switch will find which switch ports each host is plugged into and will reverse map the traffic

#  - at startup slurp the latest ibnetdiscover output to figure out
#    which switch ports are connected to HCA's
#  - run perfqueryMany commands every so often
#  - compute the rates (ignoring over/under flows)
#  - pound that info into ganglia via gmetric spoofing
#  - if it looks like new hosts have been added to the fabric, then re-run ibnetdiscover

import sys
import time
import string
import subprocess
import socket
import os
import json
import urllib.request, urllib.error, urllib.parse

# from pbsMauiGanglia import gangliaStats
from ibTracePorts import parseIbnetdiscover

# from bobMon import pbsJobs  # to find which jobs are on a flickering node
import gmetric

dir = "/root/ib/"
perfCmd = dir + "perfqueryMany"

gmondFormat = "collectl"  # use collectl style names for metrics
gmondFormat = "classic"

gmondHost = "10.8.48.11"
gmondPort = 8649
gmondProtocol = "udp"  # 'multicast'

debug = 0

# only gather from nodes that we've heard from in the last 'aliveTime' seconds
gmond_lastReported = "http://transom1.hpc.sut/bobMon/gmond_lastReported.json"
aliveTime = 120

# sleep this many seconds between samples
#  NOTE - needs to be > aliveTime to avoid nodes 'alive' with our own spoof'd data
#    .... fuckit... do it often ... sigh - fix ganglia spoofing later.
sleepTime = 15

# --host or --switch mode
hostMode = "host"

# limit insane data
dataMax = 40 * 1024 * 1024 * 1024  # 40GB/s
pktsMax = 50 * 1024 * 1024  # 3 M pkts/s is too low, try 10, try 50

# unreliable hosts
unreliable = []
# no networking on cmms
for f in range(1, 65):
    unreliable.append("cmm%d" % f)
# remove gige
for f in range(1, 27):
    unreliable.append("hamster%d" % f + "gige")
for s in ["vu-man", "gopher", "vayu"]:
    for f in range(1, 5):
        unreliable.append(s + "%d" % f + "gige")
# unreliable.append( "gopher4" )
unreliable.append("lolza")
unreliable.append("gopher4")
# unreliable.append( "vu-man3" )
unreliable.append("roffle")
unreliable.append("rofflegige")

unreliable.append("g2.hpc.swin.edu.au")
unreliable.append("hpc-mgmt-ipmi.hpc.swin.edu.au")
unreliable.append("hpc-mgmt")
unreliable.append("mds1.hpc.swin.edu.au")
unreliable.append("mds2.hpc.swin.edu.au")
unreliable.append("QLogic")  # some un-named 1/2 up node?

unreliable.append("ldap1.hpc.swin.edu.au")
unreliable.append("ldap2.hpc.swin.edu.au")

# collectl does ib on oss/mds
unreliable.append("metadata01")
unreliable.append("metadata02")
for f in range(1, 13):
    unreliable.append("object%.2d" % f)
## and on tapeserv01
# unreliable.append( "tapeserv01" )

# on gige but not IB
unreliable.append("rsldap1")
unreliable.append("rsldap2")
unreliable.append("data-mover01")
unreliable.append("data-mover02")
unreliable.append("gbkfit.hpc.swin.edu.au")
unreliable.append("gbkfit")

# ignore compute. we just gather for storage
for f in range(1, 3):
    unreliable.append("transom%d" % f)
    unreliable.append("farnarkle%d" % f)
    unreliable.append("riley%d" % f)
for f in range(1, 201):
    unreliable.append("john%d" % f)
for f in range(1, 21):
    unreliable.append("bryan%d" % f)
for f in range(1, 330):
    unreliable.append("gina%d" % f)
    unreliable.append("dave%d" % f)
    unreliable.append("data-mover%.2d" % f)
for f in range(1, 205):
    unreliable.append("gstar%.3d" % f)
for f in range(1, 302):
    unreliable.append("sstar%.3d" % f)
for f in range(1, 21):
    unreliable.append("clarke%d" % f)
unreliable.append("pbs")
unreliable.append("hpc-mgmt")
unreliable.append("sstar")
unreliable.append("gstar")
unreliable.append("phlange")
unreliable.append("tapeserv01")
unreliable.append("trevor")
for f in range(1, 101):
    unreliable.append("trevor%d" % f)
## ignore mlx side of lnet's too?
# for f in range(1,21):
#   unreliable.append( "lnet%.2d" % f )
# ignore beer for now
# unreliable.append( "metadata101" )
# unreliable.append( "object101" )
# unreliable.append( "object102" )

## router nodes
# useAnyway = [ 'knet00', 'knet01' ]

crashedOs = []
ipCache = {}


def findUpDown(all, timeout):
    now = time.time()  # seconds since 1970
    up = []
    down = []
    for host in all.keys():
        # if now - all[host]['reported'] < timeout:
        if now - all[host] < timeout:
            up.append(host)
        else:
            down.append(host)
    return up, down


def listOfUpHosts(deadTimeout):
    # g = gangliaStats( reportTimeOnly=1 )
    # all = g.getAll()
    all = json.load(urllib.request.urlopen(gmond_lastReported))

    up, down = findUpDown(all, deadTimeout)
    up.sort()
    # print 'down', down
    # print 'up', up

    # delete hosts with unreliable bmc's
    for u in unreliable:
        if u in up:
            # print 'deleting unreliable', u
            up.remove(u)
    # print 'up', up
    # sys.exit(1)

    return up


def runCommand(cmd):
    p = subprocess.Popen(
        cmd, shell=True, bufsize=-1, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = p.communicate()
    # write any errs to stderr
    if len(err):
        sys.stderr.write(sys.argv[0] + ": Error: runCommand: " + cmd[0] + " ... " + err)
    return out, err


def getIp(host):
    try:
        ip = ipCache[host]
    except:
        print("host", host, "not in ipCache")
        ip = socket.gethostbyname(host)
        ipCache[host] = ip
    return ip


def compareIbToGanglia(lidPortHost, up):
    ibHosts = []
    for swl, swp, l, p, h in lidPortHost:
        ibHosts.append(h.split()[0])  # stip off the HCA-* or whatever
    newlyDown = []
    for h in ibHosts:
        # if h in useAnyway:  # assume always up, even if not seen anywhere else
        #   if h not in up:
        #      up.append(h)
        #   continue
        if h not in up and h not in unreliable:
            if h not in crashedOs:
                crashedOs.append(h)
                newlyDown.append(h)  # print msg about this below
                sys.stderr.write(
                    sys.argv[0]
                    + ": Warning: "
                    + h
                    + " on ib but not in ganglia (will only print this once)\n"
                )
        else:
            if h in crashedOs:
                crashedOs.remove(h)
                sys.stderr.write(
                    sys.argv[0]
                    + ": Info: "
                    + h
                    + " in ib. was out of ganglia, but now back up\n"
                )

    #   #newlyDown = [ "v1205", "v1206" ]
    #   # check for multiple down nodes running the same job
    #   if len(newlyDown):
    #      p = pbsJobs()
    #      jobs = p.getJobList()
    #      j = {}
    #      for h in newlyDown:
    #         for username, nodeList, gpus, line, tagId, timeToGo, jobId, jobName, pbsInfo in jobs:  # append to joblist field
    #            if h in nodeList:
    #               if 'state' in pbsInfo.keys() and pbsInfo['state'] != 'S':
    #                  k = str( ( username, line ) )
    #                  if k not in j.keys():
    #                     j[k] = []
    #                  j[k].append(h)
    #      for h in j.keys():
    #         if len(j[h]) > 1: # more than 1 node of this job is down
    #            sys.stderr.write( sys.argv[0] + ': Warning: job ' + str(h) + ' has multiple nodes down in ganglia ' + str(j[h]) + '\n' )
    #   #sys.exit(1)

    newhosts = 0
    for h in up:
        if h not in ibHosts:
            sys.stderr.write(
                sys.argv[0] + ": Error: " + h + " up in ganglia but not on ib\n"
            )
            newhosts = 1
    # sys.exit(1)

    return newhosts


def runIbnetdiscover():
    # run this:
    #   /usr/sbin/ibnetdiscover > /root/ib/`date +'%F-%T'`.ibnetdiscover
    sys.stderr.write(sys.argv[0] + ": Info: running ibnetdiscover\n")
    r, err = runCommand("/usr/sbin/ibnetdiscover")
    if len(err) != 0:
        sys.stderr.write(sys.argv[0] + ": Error: running ibnetdiscover failed\n")
        return 1
    fn = dir + time.strftime("%Y-%m-%d-%H:%M:%S") + ".ibnetdiscover"
    try:
        f = open(fn, "w")
    except:
        sys.stderr.write(sys.argv[0] + ": Error: open of file " + fn + " failed\n")
        return 1
    try:
        f.writelines(r)
    except:
        sys.stderr.write(sys.argv[0] + ": Error: write to file " + fn + " failed\n")
        f.close()
        return 1
    f.close()
    return 0


def buildIbCmd(lidPortHost, up):
    lp = perfCmd
    cnt = 0
    for swl, swp, l, p, h in lidPortHost:
        if h.split()[0] in up:  # only gather for up hosts
            if hostMode == "host":
                lp += " %d %d" % (l, p)
            else:
                lp += " %d %d" % (swl, swp)
            cnt += 1
    return lp, cnt


def parseToStats(r, lidPortHost, up):
    # expect this ->

    # # Port counters: Lid 214 port 35
    # PortSelect:......................35
    # CounterSelect:...................0x1b01
    # PortXmitData:....................196508288843
    # PortRcvData:.....................550793773496
    # PortXmitPkts:....................6618992385
    # PortRcvPkts:.....................2242117286
    # PortUnicastXmitPkts:.............5312308102
    # PortUnicastRcvPkts:..............3582819080
    # PortMulticastXmitPkts:...........3020372621
    # PortMulticastRcvPkts:............226383425
    # timestamp 1264494583.110014

    # or (later) with an [extended] in the 1st line ->

    # # Port extended counters: Lid 61 port 35
    # PortSelect:......................35
    # CounterSelect:...................0x1b01
    # PortXmitData:....................2865699555629
    # PortRcvData:.....................5818573238645
    # PortXmitPkts:....................8450135651
    # PortRcvPkts:.....................15372362298
    # PortUnicastXmitPkts:.............8450138387
    # PortUnicastRcvPkts:..............15372365034
    # PortMulticastXmitPkts:...........0
    # PortMulticastRcvPkts:............0
    # timestamp 1279194662.416459

    # sometimes with a prefix of this
    # ibwarn: [21453] main: PerfMgt ClassPortInfo 0x400 extended counters not indicated

    # but should be able to handle

    # <some errors>
    # timestamp 1264494583.110014

    upTo = 0
    reading = 0
    s = {}
    d = None
    errCnt = 0
    for i in r:
        if i[:6] == "# Port":
            # check it's the next lid/port we're expecting
            h = ""
            while h not in up:
                swlid, swport, lid, port, h = lidPortHost[upTo]
                h = h.split()[0]
                # if h not in up:
                #   print 'skipping', h
                upTo += 1
            ii = i.split(":")[1]
            ii = ii.split()
            # print 'h', h, 'i', i
            if hostMode == "switch" and (int(ii[1]) != swlid or int(ii[3]) != swport):
                if errCnt < 1:
                    sys.stderr.write(
                        sys.argv[0]
                        + ": Error: host "
                        + h
                        + ": expected switch lid/port %d/%d" % (swlid, swport)
                        + " not "
                        + i
                        + ". Supressing further errors\n"
                    )
                errCnt += 1
                continue
            elif hostMode == "host" and (int(ii[1]) != lid or int(ii[3]) != port):
                if errCnt < 1:
                    sys.stderr.write(
                        sys.argv[0]
                        + ": Error: host "
                        + h
                        + ": expected host lid/port %d/%d" % (lid, port)
                        + " not "
                        + i
                        + ". Supressing further errors\n"
                    )
                errCnt += 1
                continue
            reading = 1
            d = []
        elif i[:9] == "timestamp":
            reading = 0
            t = float(i.split()[1])
            # print h, 'time', t
            if len(d) != 4:
                sys.stderr.write(
                    sys.argv[0]
                    + ": Error: skipping "
                    + h
                    + ": did not find 4 ib stats\n"
                )
                continue
            s[h] = (t, d)
        else:
            if not reading:
                continue
            ii = i.split(":")
            if ii[0] in ("PortXmitData", "PortRcvData", "PortXmitPkts", "PortRcvPkts"):
                val = ii[1].strip(".")
                # print h, ii[0], val
                d.append(int(val))

    # the last hosts might need to be skipped too
    h = ""
    while h not in up and upTo < len(lidPortHost):
        swlid, swport, lid, port, h = lidPortHost[upTo]
        h = h.split()[0]
        # if h not in up:
        #   print 'skipping', h
        upTo += 1

    if upTo != len(lidPortHost):
        sys.stderr.write(
            sys.argv[0]
            + ": Error: expected %d responses and got %d. ErrCnt %d\n"
            % (len(lidPortHost), upTo, errCnt)
        )
    elif errCnt:
        sys.stderr.write(sys.argv[0] + ": Error: ErrCnt %d\n" % (errCnt))

    return s


def computeRates(sOld, s):
    rates = {}
    # host, ( time, [txData, rxData, txPkts, rxPkts] )
    for h in s.keys():
        if h in sOld.keys():
            t, d = s[h]
            tOld, dOld = sOld[h]
            dt = t - tOld
            bad = 0
            r = []
            for i in range(len(d)):
                if dt <= 0.0:
                    bad = 1
                else:
                    dd = float(d[i] - dOld[i]) / dt
                    r.append(dd)
                if dd < 0.0:
                    bad = 1
            if not bad:
                rates[h] = r
    return rates


def ratesToGmetric(gm, rates, up):
    rateKeys = rates.keys()

    weirdCnt = 0
    weirdThresh = 5
    # for each host in turn...
    for i in up:
        spoofStr = getIp(i) + ":" + i

        if i not in rateKeys:
            sys.stderr.write(sys.argv[0] + ": Error: host " + i + " not in post\n")
            continue

        dd = rates[i]
        # print dd

        # units of Data are "octets divided by 4", which means bytes/4, so 1 unit is 4 bytes.
        if hostMode == "host":
            txData = dd[0] * 4.0
            rxData = dd[1] * 4.0
            txPkts = dd[2]
            rxPkts = dd[3]
        else:
            # remember to reverse rates 'cos we're looking at the switch end of the link
            txData = dd[1] * 4.0
            rxData = dd[0] * 4.0
            txPkts = dd[3]
            rxPkts = dd[2]

        if txData > dataMax or txData < 0:
            if weirdCnt < weirdThresh:
                print("trapped weird txData", txData, "host", i)
            weirdCnt += 1
            txData = 0.0
        if rxData > dataMax or rxData < 0:
            if weirdCnt < weirdThresh:
                print("trapped weird rxData", rxData, "host", i)
            weirdCnt += 1
            rxData = 0.0
        if txPkts > pktsMax or txPkts < 0:
            if weirdCnt < weirdThresh:
                print("trapped weird txPkts", txPkts, "host", i)
            weirdCnt += 1
            txPkts = 0.0
        if rxPkts > pktsMax or rxPkts < 0:
            if weirdCnt < weirdThresh:
                print("trapped weird rxPkts", rxPkts, "host", i)
            weirdCnt += 1
            rxPkts = 0.0

        if weirdCnt >= weirdThresh:
            print("trapped many weird pkts/data - cnt", weirdCnt)

        if gmondFormat == "collectl":
            gm.send(
                "iconnect.kbout",
                "%.2f" % (txData / 1024.0),
                "double",
                "kb/sec",
                "both",
                60,
                0,
                "infiniband",
                spoofStr,
            )
            gm.send(
                "iconnect.kbin",
                "%.2f" % (rxData / 1024.0),
                "double",
                "kb/sec",
                "both",
                60,
                0,
                "infiniband",
                spoofStr,
            )
            gm.send(
                "iconnect.pktout",
                "%.2f" % txPkts,
                "double",
                "packets/sec",
                "both",
                60,
                0,
                "infiniband",
                spoofStr,
            )
            gm.send(
                "iconnect.pktin",
                "%.2f" % rxPkts,
                "double",
                "packets/sec",
                "both",
                60,
                0,
                "infiniband",
                spoofStr,
            )
        else:
            if debug:
                print(
                    "gm.send( sorenson_ib_bytes_out, %.2f" % txData,
                    "double, kb/sec,      both, 60, 0, infiniband",
                    spoofStr,
                    ")",
                )
                print(
                    "gm.send( sorenson_ib_bytes_in,  %.2f" % rxData,
                    "double, kb/sec,      both, 60, 0, infiniband",
                    spoofStr,
                    ")",
                )
                print(
                    "gm.send( sorenson_ib_pkts_out,  %.2f" % txPkts,
                    "double, packets/sec, both, 60, 0, infiniband",
                    spoofStr,
                    ")",
                )
                print(
                    "gm.send( sorenson_ib_pkts_in,   %.2f" % rxPkts,
                    "double, packets/sec, both, 60, 0, infiniband",
                    spoofStr,
                    ")",
                )
            else:
                gm.send(
                    "sorenson_ib_bytes_out",
                    "%.2f" % txData,
                    "double",
                    "kb/sec",
                    "both",
                    60,
                    0,
                    "infiniband",
                    spoofStr,
                )
                gm.send(
                    "sorenson_ib_bytes_in",
                    "%.2f" % rxData,
                    "double",
                    "kb/sec",
                    "both",
                    60,
                    0,
                    "infiniband",
                    spoofStr,
                )
                gm.send(
                    "sorenson_ib_pkts_out",
                    "%.2f" % txPkts,
                    "double",
                    "packets/sec",
                    "both",
                    60,
                    0,
                    "infiniband",
                    spoofStr,
                )
                gm.send(
                    "sorenson_ib_pkts_in",
                    "%.2f" % rxPkts,
                    "double",
                    "packets/sec",
                    "both",
                    60,
                    0,
                    "infiniband",
                    spoofStr,
                )


def parseArgs():
    global hostMode

    if len(sys.argv) != 2:
        print("needs --host or --switch")
        sys.exit(1)
    if sys.argv[1] == "--host":
        hostMode = "host"
    elif sys.argv[1] == "--switch":
        hostMode = "switch"
    else:
        print("needs --host or --switch")
        sys.exit(1)


if __name__ == "__main__":
    first = 1

    parseArgs()

    gm = gmetric.Gmetric(gmondHost, gmondPort, gmondProtocol)

    blah, blah, lidPortHost, blah = parseIbnetdiscover()
    # print 'lidPortHost,', lidPortHost, 'len(lidPortHost)', len(lidPortHost)

    sOld = {}
    netdiscoverLoop = 0
    while 1:
        if not first:
            time.sleep(sleepTime)

        up = listOfUpHosts(aliveTime)
        # hack ->
        # up = []
        # for i in range(1033,1152+1):
        #   up.append( 'v%d' % i )
        # if first:
        #   print 'up', up

        if not len(up):
            continue

        newNodesFound = compareIbToGanglia(lidPortHost, up)
        if newNodesFound:
            netdiscoverLoop += 1
            if netdiscoverLoop in (1, 2, 10, 100, 1000):
                print("netdiscover loop", netdiscoverLoop)
                fail = runIbnetdiscover()
                if fail:
                    sys.stderr.write(
                        sys.argv[0] + ": Error: runIbnetdiscover failed. sleeping 30s\n"
                    )
                    time.sleep(30)
                    continue
                blah, blah, lidPortHost, blah = parseIbnetdiscover()
                continue
        else:
            netdiscoverLoop = 0

        cmd, cnt = buildIbCmd(lidPortHost, up)
        # print 'cmd', cmd, 'cnt', cnt
        # print 'up', up, 'len(up)', len(up)

        # run ibperf
        r, err = runCommand(cmd)
        r = r.split("\n")
        # print 'r', r, 'len(r)', len(r)

        s = parseToStats(r, lidPortHost, up)
        # print 's', s, 'len(s)', len(s)

        rates = computeRates(sOld, s)
        # print 'rates', rates, 'len(rates)', len(rates)
        sOld = s

        if first:
            first = 0
            continue

        # debug - don't send to gmetric
        # continue
        # up = [ 'gstar001' ]
        # print 'rates[star001]', rates['gstar001']
        # continue

        ratesToGmetric(gm, rates, up)

        # sys.exit(1)
