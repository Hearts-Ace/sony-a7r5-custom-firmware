"""Generate a path-only resource directory on a separate Git branch, no Pages build."""
from pathlib import Path
import json
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def git(*args, input=None):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], input=input).decode().strip()


def publish():
    revision = git('rev-parse', 'HEAD')
    # Git quotes non-ASCII names unless core.quotepath is disabled.
    paths = git('-c', 'core.quotepath=false', 'ls-tree', '-r', '--name-only', revision, '--', 'filters', 'm4-filters', 'c2-filters', 'filter-bundles', 'resource-info').splitlines()
    document = dict(schema='r5-resource-directory/1', revision=revision,
                    revision_time=int(git('show', '-s', '--format=%ct', revision)), paths=paths)
    data = (json.dumps(document, ensure_ascii=False, indent=2)+'\n').encode()
    blob = git('hash-object', '-w', '--stdin', input=data)
    tree = git('mktree', input=f'100644 blob {blob}\tdirectory.json\n'.encode())
    previous = git('ls-remote', 'origin', 'refs/heads/resource-index')
    parents = []
    if previous:
        git('fetch', '--quiet', 'origin', 'resource-index')
        parent = previous.split()[0]
        if git('rev-parse', f'{parent}^{{tree}}') == tree:
            print('Resource directory already current'); return
        parents = ['-p', parent]
    commit = git('-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com',
                 'commit-tree', tree, *parents, input=b'Update current resource directory\n')
    subprocess.run(['git', '-C', str(ROOT), 'push', 'origin', f'{commit}:refs/heads/resource-index'], check=True)
    print(f'Published resource paths for {revision}; no Pages deployment')
    # The branch pointer is mutable; invalidate CDN metadata after daily updates.
    try:
        url = 'https://purge.jsdelivr.net/gh/Hearts-Ace/sony-a7r5-custom-firmware@resource-index/directory.json'
        with urllib.request.urlopen(url, timeout=30) as response:
            result = json.load(response)
        print('CDN directory invalidation requested:', result.get('status'))
    except Exception as error:
        print(f'CDN invalidation unavailable; normal cache expiry applies: {error}')


if __name__ == '__main__':
    publish()
