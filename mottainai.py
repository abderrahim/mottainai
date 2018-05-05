import re, os, sys, subprocess
from ruamel.yaml import safe_load
from buildstream.utils import url_directory_name

# functions that load buildstream files
def load_project_conf(commit):
    projectconf = safe_load(get_file_contents(commit, 'project.conf'))

    return projectconf['aliases'], projectconf['element-path']

def get_sourcedir():
    buildstreamconf = safe_load(open(os.path.expanduser('~/.config/buildstream.conf')))

    if 'sourcedir' in buildstreamconf:
        return buildstreamconf['sourcedir']
    else:
        return os.path.expanduser('~/.cache/buildstream/sources/')

# functions that call to git
git_diffstat = ['git', 'diff', '--stat']
git_lstree =  ['git', 'ls-tree']
git_catfile = ['git', 'cat-file', 'blob']

def get_file_contents(commit, filename):
    #print(git_lstree + [commit, filename])
    lstree = subprocess.check_output(git_lstree + [commit, filename])
    if lstree:
        sha = lstree.split()[-2]
        contents = subprocess.check_output(git_catfile + [sha])
        return contents
    return ''

pat = re.compile(' ([^ ]+)?({([^ ]+) => ([^ ]+)})?([^ ]+)?.bst +\| .*')

def get_changed_files(commit1, commit2):
    diffstat = subprocess.check_output(git_diffstat + [commit1, commit2])
    for l in diffstat.splitlines()[:-1]:
        m = pat.match(l.decode())
        
        if m is None:
            continue

        file1 = construct_filename(m.group(1), m.group(3), m.group(5)) + '.bst'
        file2 = construct_filename(m.group(1), m.group(4), m.group(5)) + '.bst'

        yield file1, file2


# pure functions
def construct_filename(*parts):
    return os.path.join(*[part for part in parts if part])

def extract_urls(yml, kind):
    return [src['url'] for src in yml['sources'] if src['kind'] == kind]

def resolve_url(url, aliases):
    scheme, path = url.split(':')
    if scheme in aliases:
        return aliases[scheme] + path
    else:
        return aliases

def detect_difference(old, new, kind):
    if 'sources' not in old or 'sources' not in new:
        return None, None

    oldsources = extract_urls(old, kind)
    newsources = extract_urls(new, kind)
    
    if not oldsources or not newsources:
        return None, None

    if len(oldsources) > 1 or len(newsources) > 1:
        print("warning: element %s has more than one %s source", file1 if file1 == file2 else (file1, file2))

    return oldsources[0], newsources[0]


if __name__ == '__main__':
    if len(sys.argv) == 1 or len(sys.argv) > 3:
        print('usage: %s <commitrange>')
        raise SystemExit

    if len(sys.argv) == 2:
        commit1, commit2 = sys.argv[1].split('..')
    else:
        commit1, commit2 = sys.argv[1:]

    aliases1, elementpath1 = load_project_conf(commit1)
    aliases2, elementpath2 = load_project_conf(commit2)

    sourcedir = get_sourcedir()

    for file1, file2 in get_changed_files(commit1, commit2):
        #print(file1, file2)
        old = safe_load(get_file_contents(commit1, file1))
        new = safe_load(get_file_contents(commit2, file2))
        
        if not old or not new:
            continue

        for kind in ('git', 'ostree'):
            oldurl, newurl = detect_difference(old, new, kind)

            if oldurl is None or newurl is None:
                continue

            def dirpath(url, aliases):
                dirname = url_directory_name(resolve_url(url, aliases))
                return os.path.join(sourcedir, kind, dirname)

            print('mv', dirpath(oldurl, aliases1), dirpath(newurl, aliases2))
