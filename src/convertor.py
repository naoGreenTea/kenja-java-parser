import os
from git import Repo
from git import Blob
from exc import InvalidHistoragePathException
from subprocess import (
                            Popen,
                            PIPE,
                            check_output
                        )
import shutil
from parser import ParserExecutor

class HistorageConverter:
    parser_jar_path = "../target/kenja-0.0.1-SNAPSHOT-jar-with-dependencies.jar" 
    
    def __init__(self, org_git_repo, new_git_repo_dir_path, working_dir):
        dirname = os.path.basename(new_git_repo_dir_path)
        if(dirname == '.git'):
            raise InvalidHistoragePathException('Do not use ".git" dir for historage path')

        if os.path.exists(new_git_repo_dir_path):
            raise InvalidHistoragePathException( \
                    '%s is already exists. Historage converter will be create new directory and git repository automatically' \
                    % (new_git_repo_dir_path))

        self.historage_repo = Repo.init(new_git_repo_dir_path)
        self.org_repo = org_git_repo
        
        if not(os.path.isdir(working_dir)):
            raise Exception('%s is not a directory' % (working_dir))
        self.working_dir = working_dir

        self.syntax_trees_dir = os.path.join(self.working_dir, 'syntax_trees')
        self.parser_executor = ParserExecutor(self.syntax_trees_dir, self.parser_jar_path)

    def parse_all_java_files(self):
        self.changed_commits = []
        for commit in self.org_repo.iter_commits(self.org_repo.head):
            for p in commit.parents:
                changed = False
                for diff in p.diff(commit):
                    if diff.a_blob and diff.a_blob.name.endswith(".java"):
                        changed = True
                    if diff.b_blob and diff.b_blob.name.endswith(".java"):
                        #self.parser_executor.parse_blob(diff.b_blob)
                        changed = True
                if changed:
                    self.changed_commits.append(commit.hexsha)

    def remove_files(self, repo, index, removed_files):
        kwargs = {"r" : True}
        if len(removed_files) == 0:
            return
        index.remove(removed_files, **kwargs)
        index.write()

        for p in removed_files:
            shutil.rmtree(os.path.join(repo.working_dir, p))

    def add_files(self, repo, index, added_files):
        if len(added_files) == 0:
            return

        for path, hexsha in added_files.items():
            src = os.path.join(self.syntax_trees_dir, hexsha)
            dst = os.path.join(repo.working_dir, path)
            shutil.copytree(src, dst)

        repo.git.add(added_files.keys())
        index.update()

    def is_completed_parse(self, blob):
        path = os.path.join(self.working_dir, 'syntax_trees', blob.hexsha)
        cmd = ['find', path, '-type', 'f']
        output = check_output(cmd)
        if len(output) == 0:
            print 'Interface?:', blob.path
        return len(output) > 0

    def construct_from_commit(self, repo, commit):
        added_files = {}
        for entry in commit.tree.traverse():
            if not isinstance(entry, Blob):
                continue

            if not entry.name.endswith('.java'):
                continue

            added_files[entry.path] = entry.hexsha

        self.add_files(repo, repo.index, added_files)
        repo.index.commit(commit.hexsha)

    def commit_syntax_trees(self, repo, start, end):
        for i in range(start, end + 1):
            commit = self.org_repo.commit(self.changed_commits[i])

            if i == start:
                self.construct_from_commit(repo, commit)
            else:
                self.apply_change(repo, commit)

    def apply_change(self, new_repo, commit):
        assert len(commit.parents) < 2 # Not support branched repository

        index = new_repo.index
        removed_files = []
        added_files = {}
        for p in commit.parents:
            for diff in p.diff(commit):
                if(diff.a_blob):
                    if not diff.a_blob.name.endswith(".java"):
                        continue
                    if self.is_completed_parse(diff.a_blob):
                        removed_files.append(diff.a_blob.path)

                if(diff.b_blob):
                    if not diff.b_blob.name.endswith(".java"):
                        continue
                    if self.is_completed_parse(diff.b_blob):
                        added_files[diff.b_blob.path] = diff.b_blob.hexsha

            print 'removed:', removed_files
            self.remove_files(repo, index, removed_files)

            print 'added:', added_files
            self.add_files(repo, index, added_files)

        if len(index.diff(None, staged=True)):
            print 'committing...'
            index.commit(commit.hexsha)

    
    def divide_commits(self, num):
        self.changed_commits.reverse()
        num_commits = len(self.changed_commits)
        step = num_commits // num
        starts = range(0, num_commits, step)
        ends = range(0 + step - 1, num_commits, step) 
        ends[-1] = num_commits - 1
        if(starts > num):
            starts.pop()
        
        return(starts, ends)

    def prepare_base_repo(self):
        base_repo_dir = os.path.join(self.working_dir, 'base_repo')
        self.base_repo = Repo.init(base_repo_dir)
        open(os.path.join(base_repo_dir, 'historage_dummy'), 'w').close()
        self.base_repo.index.add(['historage_dummy'])
        self.base_repo.index.commit('Initail dummy commit')

    def clone_working_repos(self, num):
        self.working_repos = []
        for i in range(num):
            working_repo_dir = os.path.join(self.working_dir, 'work_repo%d' % (i))
            self.working_repos.append(self.base_repo.clone(working_repo_dir))

    def commit_all_syntax_trees(self):
        arg = {'reverse':True}
        for commit in self.org_repo.iter_commits(self.org_repo.head, **arg):
            print 'process commit:', commit.hexsha
            self.apply_change(self.historage_repo, commit)

    def parse_blob(self, blob):
        blob.data_stream.read()
        cmd = "java "
        cmd += "-cp " + self.kenja_jar
        cmd += self.kenja_parser_class
        cmd += self.kenja_outpu_dir + blob.hexsha

        p = Popen(cmd.split(' '), stdin=PIPE)
        p.stdin.write(blob.data_stream.read())
        return p

    def convert(self):
        print 'create paresr processes...'
        self.parse_all_java_files()

        print len(self.changed_commits)
        
        self.prepare_base_repo()
        self.clone_working_repos(10)

        (starts, ends) = self.divide_commits(10)
        for i in range(len(starts)):
            print 'process %d th repo...' % (i)
            self.commit_syntax_trees(self.working_repos[i], starts[i], ends[i])

        print 'waiting parser processes'
        #self.parser_executor.join()

        print 'create historage...'
        #self.commit_all_syntax_trees()

if __name__ == '__main__':
    import argparse
 
    parser = argparse.ArgumentParser(description='Git Blob Parser')
    parser.add_argument('org_git_dir')
    parser.add_argument('new_git_repo_dir')
    parser.add_argument('syntax_trees_dir')

    args = parser.parse_args()
    
    git_dir = args.org_git_dir
    if not os.path.isdir(git_dir):
        print "%s is not a directory" % (git_dir)

    repo = Repo(git_dir)
    
    gbp = HistorageConverter(repo, args.new_git_repo_dir, args.syntax_trees_dir)
    gbp.convert()