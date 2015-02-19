import subprocess

def _parse_commits(v):
    commit = ''
    for line in v.split('\n'):
        line = line.rstrip()
        #if re.match('commit ')
    pass


def _get_commits():
    GIT_COMMIT_FIELDS = ['id', 'author_name', 'author_email', 'date', 'message']
    GIT_LOG_FORMAT = ['%H', '%an', '%ae', '%ad', '%s']
    GIT_LOG_FORMAT = '%x1f'.join(GIT_LOG_FORMAT) + '%x1e'
    p = subprocess.Popen('git log -10 --format="%s"' % GIT_LOG_FORMAT, shell=True, stdout=subprocess.PIPE)
    (log, _) = p.communicate()
    log = log.strip('\n\x1e').split("\x1e")
    log = [row.strip().split("\x1f") for row in log]
    log = [dict(zip(GIT_COMMIT_FIELDS, row)) for row in log]

    return log
