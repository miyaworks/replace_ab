#! /usr/bin/env/python2.6
# --* coding:utf-8 *--


__author__ = "tyy"

import argparse
import gevent
import urlparse
import time
from collections import defaultdict, namedtuple
from requests.packages.urllib3.util import parse_url
from socket import gethostbyname, gaierror
from gevent.pool import Pool

class RunResults(object):
    """Encapsulates the results of a single test.
    Contains a dictionary of status codes to lists of request durations,
    a list of exception instances raised during the run, the total time.
    """
    def __init__(self):
	self.status_code_counter = defaultdict(list)
        self.errors = []
        self.total_time = None


RunStats = namedtuple('RunStats', ['count', 'total_time', 'rps', 'avg', 'min','max', 'amp', 'stdev'])


def calc_stats(results):
    """Calculate stats (min, max, avg) from the given RunResults.

       The statistics are returned as a RunStats object.
    """
    all_res = []
    count = 0
    for values in results.status_code_counter.values():
        all_res += values
        count += len(values)

    cum_time = sum(all_res)

    if cum_time == 0 or len(all_res) == 0:
        rps = avg = min_ = max_ = amp = stdev = 0
    else:
        if results.total_time == 0:
            rps = 0
        else:
            rps = len(all_res) / float(results.total_time)
        avg = sum(all_res) / len(all_res)
        max_ = max(all_res)
        min_ = min(all_res)
        amp = max(all_res) - min(all_res)
        stdev = math.sqrt(sum((x-avg)**2 for x in all_res) / count)

    return (RunStats(count, results.total_time, rps, avg, min_, max_, amp, stdev))


def print_stats(results):
    """
    print the test results
    """
    stats = calc_stats(results)
    rps = stats.rps

    print('')
    print('-------- Results --------')

    print('Successful calls\t\t%r' % stats.count)
    print('Total time        \t\t%.4f s  ' % stats.total_time)
    print('Average           \t\t%.4f s  ' % stats.avg)
    print('Fastest           \t\t%.4f s  ' % stats.min)
    print('Slowest           \t\t%.4f s  ' % stats.max)
    print('Amplitude         \t\t%.4f s  ' % stats.amp)
    print('Standard deviation\t\t%.6f' % stats.stdev)
    print('RPS               \t\t%d' % rps)
    if rps > 500:
        print('BSI              \t\tWoooooo Fast')
    elif rps > 100:
        print('BSI              \t\tPretty good')
    elif rps > 50:
        print('BSI              \t\tMeh')
    else:
        print('BSI              \t\tHahahaha')
    print('')
    print('-------- Status codes --------')
    for code, items in results.status_code_counter.items():
        print('Code %d          \t\t%d times.' % (code, len(items)))
    print('')
    print('-------- Legend --------')
    print('RPS: Request Per Second')
    print('BSI: Boom Speed Index')


def resolve(url):
    """
    parse the url to dns resolution
    """
    parts = parse_url(url)
    if not parts.port and parts.scheme == 'https':
	port = 443
    if not parts.port and parts.scheme == 'http':
	port = 80
    else:
	port = parts.port
    original = parts.host
    resolved = gethostbyname(parts.host)
    host = resolved if parts.scheme != 'https' else parts.host
    netloc = '%s:%d' % (host, port) if port else host
    return (urlparse.urlunparse((parts.scheme, netloc, parts.path or '', '', parts.query or '',\
           parts.fragment or '')), original, host)

def onecall(method,url,results):
    """
    performs a single HTTP call and puts the result into the status_code_counter.    
    """

    start = time.time()
    try:
	res = method(url)
    except RequestException as exc:
        results.errors.append(exc)
    else:
        duration = time.time() - start
        results.status_code_counter[res.status_code].append(duration)
	

def run(url,requests=1,concurrency=1):
    pool = Pool(concurrency)
    start = time.time()
    jobs = None
    res = RunResults()
    try:
	jobs = [pool.spawn(onecall,'GET',url,res)for i in range(requests)]
	pool.join()
    except KeyboardInterrupt:
	pass
    finally:
	res.total_time = time.time() - start
    
    return res


def load(url, requests, concurrency):
    print url
    print('Running %d queries - concurrency %d' % (requests,concurrency))
    print "------Starting the load------"
    try:
	return run(url,requests,concurrency)
    finally:
	print "Done"

def main():
    parser = argparse.ArgumentParser(description='Simple HTTP Load runner.')
    parser.add_argument('-c','--concurrency',help='Concurrency',type=int,default=1)
    parser.add_argument('-n','--requests',help='Number of requests',type=int,default=1)
    parser.add_argument('url', help='URL to hit', nargs='?')
    args = parser.parse_args()

    if args.url is None:
        print('You need to provide an URL.')
        parser.print_usage()
        sys.exit(0)
    try:
        url,original, resolved = resolve(args.url)
    except gaierror as e:
        print(("DNS resolution failed for %s (%s)" %
                      (args.url, str(e)),))
        sys.exit(1)
    try:
	res = load(url,args.requests,args.concurrency)
    except RequestException as e:
	print e
	sys.exit(1)

    print_stats(res)

if __name__ == '__main__':
	main()
