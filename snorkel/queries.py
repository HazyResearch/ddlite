import random
from .models.context import Corpus
from .models.annotation import AnnotationKeySet, AnnotationKey


def split_corpus(session, corpus, train=0.8, development=0.1, test=0.1, seed=None):
    if train + development + test != 1.0:
        raise ValueError("Values for train + development + test must sum to 1")

    if seed is not None:
        random.seed(seed)
    docs = [doc for doc in corpus.documents]
    random.shuffle(docs)

    n = len(docs)
    num_train = int(round(train * n))
    num_development = int(round(development * n))
    num_test = n - (num_train + num_development)

    if num_train > 0:
        train_corpus = Corpus(name=corpus.name + ' Training')
        for doc in docs[:num_train]:
            train_corpus.append(doc)
        session.add(train_corpus)
        print "%d Documents added to corpus %s" % (len(train_corpus), train_corpus.name)

    if num_development > 0:
        development_corpus = Corpus(name=corpus.name + ' Development')
        for doc in docs[num_train:num_train + num_development]:
            development_corpus.append(doc)
        session.add(development_corpus)
        print "%d Documents added to corpus %s" % (len(development_corpus), development_corpus.name)

    if num_test > 0:
        test_corpus = Corpus(name=corpus.name + ' Test')
        for doc in docs[num_train + num_development:]:
            test_corpus.append(doc)
        session.add(test_corpus)
        print "%d Documents added to corpus %s" % (len(test_corpus), test_corpus.name)

    session.commit()


def get_or_create_single_key_set(session, name):
    key_set = session.query(AnnotationKeySet).filter(AnnotationKeySet.name == name).first()
    if key_set is None:
        key_set = AnnotationKeySet(name=name)
        session.add(key_set)
        session.commit()

    if len(key_set) > 1:
        raise ValueError('AnnotationKeySet with name ' + unicode(name) + ' already exists and has more than one ' +
                         'AnnotationKey. Please specify a new name.')
    elif len(key_set) == 1:
        if key_set.keys[0].name == name:
            key = key_set.keys[0]
        else:
            raise ValueError('AnnotationKeySet named ' + unicode(name) + ' already exists and has one ' +
                             'AnnotationKey with a different name. Please specify a new name.')
    else:
        key = session.query(AnnotationKey).filter(AnnotationKey.name == name).first()
        if key is None:
            key = AnnotationKey(name=name)
            session.add(key)
            session.commit()
        key_set.append(key)
        session.commit()
    return key_set, key
