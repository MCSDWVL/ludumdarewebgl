import urllib2, re, os, urlparse, sys, socket, json
from multiprocessing.dummy import Pool as ThreadPool
from threading import Lock

socket.setdefaulttimeout(10)

def scrape_ld(ld_num, dest_folder=None):
    
    lock = Lock()
    entry_re = re.compile(r"<a href='\?action=(\w+)&uid=([0-9]+)'><img src='([^']*)'><div class='title'><i>(.*?)</i></div>(.*?)</a></div>")
    target_re = re.compile(r'href=\'([^\']+)\' target=\'_blank\'>([^<]+)</a>')
    
    if dest_folder is None:
        dest_folder = "%d/thumbs/" % ld_num
    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)
        
    def get_page(url, timeout=10):
        for tries in range(3):
            try:
                f = urllib2.urlopen(url, timeout=timeout)
                contents = f.read().decode('utf-8','replace')
                f.close()
                return contents
            except Exception as e:
                with lock:
                    print >> sys.stderr, "ERROR getting %s #%d: %s" % (url, tries, e)
        else:
            raise e

    def get_games_on_page(url):
        return entry_re.findall(get_page(url))
        
    def get_game(entry):
        action,uid,thumburl,title,author = entry
        author = author.encode('ascii','replace')
        title = title.encode('ascii','replace')
        
        # get targets
        url = 'http://www.ludumdare.com/compo/ludum-dare-%s/?action=%s&uid=%s' % (ld_num, action, uid)
        contents = get_page(url)
        contents = contents.partition("<h2>Comments</h2>")[0] # strip off comments
        jam = "</strong></a> - <i>Jam Entry</i></div>" in contents
        contents = contents.partition("<h2>Downloads and Links</h2>")[2]
        contents = contents.partition("</ul>")[0]
        targets, web, unity, unity_web_gl = [], False, False, False
        for path, target in target_re.findall(contents):
            targets.append(target)
            target = target.lower()
            unity |= "unity" in target
            web |= "web" in target
            unity_web_gl = "web_gl" in path
        unity_fool = False
        if unity_web_gl:
            with lock:
                print >> sys.stderr, "Found Unity web_gl:", uid, targets
        if web and not unity: # see if we're being fooled
            for path, target in target_re.findall(contents):
                if "web" in target.lower() and not path.startswith("https://copy.com") and not path.startswith("http://www.newgrounds"): # blacklist those that have hung the script before
                    try:
                        unity |= "unity3d.com" in get_page(path).lower()
                    except Exception as e:
                        with lock:
                            print >> sys.stderr, "ERROR checking for Unity %s: %s %s" % (uid, path, e)
            if unity:
                unity_fool = True
                #with lock:
                #    print >> sys.stderr, "WARNING found a Unity game keeping quiet:", uid, targets
        if web and unity and not unity_web_gl: # see if we're being fooled about unity web_gl
            for path, target in target_re.findall(contents):
                if "web" in target.lower() and not path.startswith("https://copy.com") and not path.startswith("http://www.newgrounds"): # blacklist those that have hung the script before
                    try:
                        unity_web_gl |= "unityconfig.js" in get_page(path).lower()
                    except Exception as e:
                        with lock:
                            print >> sys.stderr, "ERROR checking for Unity web gl %s: %s %s" % (uid, path, e)
            if unity_web_gl:
                with lock:
                    print >> sys.stderr, "WARNING quiet about web_gl:", uid, targets
        return (action,uid,title,author,jam,targets,web,unity,unity_fool,unity_web_gl)
        
    game_matches = []
    game_count = 0
    pool = ThreadPool(5)        
    while True:
        page = entries_page_url_template = "http://www.ludumdare.com/compo/ludum-dare-%d/?action=preview&etype=&start=%d" % (ld_num, game_count)
        with lock:
            print "%d: getting games on page: %s"%(game_count,page)
        page_matches = get_games_on_page(page)
        if 0==len(page_matches):
            with lock:
                print "done!",len(game_matches),"games found."
            break
        game_count += len(page_matches)
        game_matches.extend(pool.map(get_game,page_matches))
    return game_matches


if __name__=="__main__":
    #opts, args = getopt.getopt(sys.argv[1:],"",
    #    ("ld-num=")
    #opts = dict(opts)
    #ld_num = int(opts.get("--ld-num","33"))
    ld_num = 33
    index_file = "%d/games.json"%ld_num 
    index = scrape_ld(ld_num)
    with open(index_file,"w") as out:
        json.dump(index,out)
