import atexit
import glob
import os
import re
import requests
import signal
import time
import warnings
from bs4 import BeautifulSoup
from collections import namedtuple, defaultdict
from subprocess import Popen


Sentence = namedtuple('Sentence', 'words, lemmas, poses, dep_parents, dep_labels')


class SentenceParser:
    def __init__(self):
        # http://stanfordnlp.github.io/CoreNLP/corenlp-server.html
        # Spawn a StanfordCoreNLPServer process that accepts parsing requests at an HTTP port.
        # Kill it when python exits.
        # This makes sure that we load the models only once.
        # In addition, it appears that StanfordCoreNLPServer loads only required models on demand.
        # So it doesn't load e.g. coref models and the total (on-demand) initialization takes only 7 sec.
        self.port = 12345
        cmd = ['java -Xmx4g -cp "parser/*" edu.stanford.nlp.pipeline.StanfordCoreNLPServer --port %d' % self.port]
        self.server_pid = Popen(cmd, shell=True).pid
        # Wait a bit for java to start up.
        time.sleep(0.5)
        atexit.register(self._kill_pserver)
        self.endpoint = 'http://localhost:%d/?properties={"annotators": "tokenize,ssplit,pos,lemma,depparse", "outputFormat": "conll"}' % self.port

    def _kill_pserver(self):
        if self.server_pid is not None:
            os.kill(self.server_pid, signal.SIGTERM)

    def parse(self, doc):
        """Parse a raw document as a string into a list of sentences"""
        resp = requests.post(self.endpoint, data=doc, allow_redirects=True)
        blocks = resp.content.strip().split('\n\n')
        for block in blocks:
            lines = block.split('\n')
            parts = defaultdict(list)
            for line in lines:
                vals = line.split('\t')
                for i, key in enumerate(['', 'words', 'lemmas', 'poses', '', 'dep_parents', 'dep_labels']):
                    if not key:
                        continue
                    val = vals[i]
                    if key == 'dep_parents':
                        val = int(val)
                    parts[key].append(val)
            sent = Sentence(**parts)
            yield sent
            
'''
Abstract base class for file type parsers
Must implement method inidicating if file can be parsed and parser
'''
class FileTypeParser:
    def can_parse(self, f):
        raise NotImplementedError()
    def parse(self, f):
        raise NotImplementedError()
        
'''
HTML parser using BeautifulSoup
'''
class HTMLParser(FileTypeParser):
    def can_parse(self, fp):
        return fp.endswith('.html')
    def parse(self, fp):
        with open(fp, 'rb') as f:
            mulligatawny = BeautifulSoup(f)
        txt = filter(self._cleaner, mulligatawny.findAll(text=True))
        return ' '.join(self._strip_special(s) for s in txt if s != '\n')
    def _cleaner(self, s):
        if s.parent.name in ['style', 'script', '[document]', 'head', 'title']:
            return False
        elif re.match('<!--.*-->', unicode(s)):
            return False
        return True
    def _strip_special(self, s):
        return ''.join(c for c in s if ord(c) < 128)
        

'''
Wrapper for a FileTypeParser that parses a file, directory, or pattern
Defaults to using HTMLParser
'''
class DocParser: 
    def __init__(self, path, ftparser = HTMLParser()):
        self.path = path
        self._ftparser = ftparser
        self._fs = self._get_files()
        
    # Parse all docs parseable by passed file type parser
    def parseDoc(self):
        docs = []
        for fn in self._fs:
            f = os.path.join(self.path, fn)
            if self._ftparser.can_parse(f):
                docs.append(self._ftparser.parse(f))
            else:
                warnings.warn("Skipping imparseable file {}".format(f))
        return docs
    
    # Use SentenceParser to return parsed sentences
    def parseDocSentences(self):
        sentences = []
        sp = SentenceParser()
        for txt in self.parseDoc():
            sentences.append(sp.parse(txt))
        return sentences
    
    def _get_files(self):
        if os.path.isfile(self.path):
            return [self.path]
        elif os.path.isdir(self.path):
            return os.listdir(self.path)
        else:
            return glob.glob(self.path)
            
    def __repr__(self):
        return "Document parser for files: {}".format(self._fs)
        

def main():
    doc = 'Hello world. How are you?'
    parser = SentenceParser()
    for s in parser.parse(doc):
        print s


if __name__ == '__main__':
    main()
