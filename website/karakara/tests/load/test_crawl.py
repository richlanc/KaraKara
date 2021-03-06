
import datetime
import resource
from bs4 import BeautifulSoup

from karakara.tests.conftest import slow


def get_ram():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024


@slow
def test_crawl(app, tracks, random_tracks):
    """
    Test to:
      - Populate the database with shit loads of data
      - crawl every possible url

    cache will put every api return in memory.
    measure how much ram is taken and how much time is taken
    """
    ram_start = get_ram()

    to_crawl = set()
    crawled = {'', None}

    to_crawl.add('/')

    def get_page_html(url):
        if not url.startswith('/') or url.startswith('/files/'):
            return ''
        response = app.get(url)
        if response.status_code == 302:
            response = response.follow()
        return response.text

    time_start = datetime.datetime.now()
    #import pdb ; pdb.set_trace()
    while to_crawl:
        url = to_crawl.pop()
        page_html = get_page_html(url)
        if not page_html:
            continue
        crawled.add(url)
        soup = BeautifulSoup(page_html)
        to_crawl |= {a.get('href') for a in soup.findAll('a')} - crawled
    time_end = datetime.datetime.now()
    pages = len(crawled)
    time_taken = time_end-time_start
    ram_end = get_ram()

    from pprint import pprint
    pprint(crawled)
    print('Crawled: {0} in {1} ({2:.2f} page/sec)'.format(pages, time_taken, pages/time_taken.total_seconds()))
    print('RAM Start: {0:.1f}, End: {1:.1f}, Change: {2:.1f} Megabytes'.format(ram_start, ram_end, ram_end-ram_start))
