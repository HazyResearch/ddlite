from .meta import SnorkelBase, snorkel_postgres
from sqlalchemy import Column, String, Integer, Table, Text, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship, backref
from sqlalchemy.types import PickleType
from sqlalchemy.inspection import inspect
from sqlalchemy.orm.session import object_session
from sqlalchemy.sql import select, text
import pickle
import pandas as pd


corpus_document_association = Table('corpus_document_association', SnorkelBase.metadata,
                                    Column('corpus_id', Integer, ForeignKey('corpus.id')),
                                    Column('document_id', Integer, ForeignKey('document.id')))


class Corpus(SnorkelBase):
    """
    A set of Documents, uniquely identified by a name.

    Corpora have many-to-many relationships with Documents, so users can create new
    subsets, supersets, etc.
    """
    __tablename__ = 'corpus'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    documents = relationship('Document', secondary=corpus_document_association, backref='corpora')
    # TODO: What should the cascades be?

    def append(self, item):
        self.documents.append(item)

    def remove(self, item):
        self.documents.remove(item)

    def __repr__(self):
        return "Corpus (" + unicode(self.name) + ")"

    def __iter__(self):
        """Default iterator is over self.documents"""
        for doc in self.documents:
            yield doc

    def __len__(self):
        return len(self.documents)

    def stats(self):
        """Print summary / diagnostic stats about the corpus"""
        print "Number of documents:", len(self.documents)
        self.child_context_stats(Document)

    def child_context_stats(self, parent_context):
        """
        Given a parent context class, gets all the child context classes, and returns histograms of the number
        of children per parent.
        """
        session = object_session(self)
        parent_name = parent_context.__table__.name

        # Get all the child context relationships
        rels = [r for r in inspect(parent_context).relationships if r.back_populates == parent_name]
        
        # Print the histograms for each child context, and recurse!
        for rel in rels:
            c  = rel.mapper.class_
            fk = list(rel._calculated_foreign_keys)[0]
                
            # Query for average number of child contexts per parent context
            label = 'Number of %ss per %s' % (c.__table__.name, parent_name)
            query = session.query(fk, func.count(c.id).label(label)).group_by(fk) 
                
            # Render as panadas dataframe histogram
            df = pd.read_sql(query.statement, query.session.bind)
            df.hist(label)

            # Recurse to grandchildren
            self.child_context_stats(c)


class Context(SnorkelBase):
    """
    A piece of content from which Candidates are composed.
    """
    __tablename__ = 'context'
    id = Column(Integer, primary_key=True)
    type = Column(String, nullable=False)
    stable_id = Column(String, unique=True, nullable=False)

    __mapper_args__ = {
        'polymorphic_identity': 'context',
        'polymorphic_on': type
    }


class Document(Context):
    """
    A root Context.
    """
    __tablename__ = 'document'
    id = Column(Integer, ForeignKey('context.id'), primary_key=True)
    name = Column(String, unique=True, nullable=False)
    meta = Column(PickleType)

    __mapper_args__ = {
        'polymorphic_identity': 'document',
    }

    def __repr__(self):
        return "Document " + unicode(self.name)


class Sentence(Context):
    """A sentence Context in a Document."""
    __tablename__ = 'sentence'
    id = Column(Integer, ForeignKey('context.id'), primary_key=True)
    document_id = Column(Integer, ForeignKey('document.id'))
    document = relationship('Document', backref=backref('sentences', cascade='all, delete-orphan'), foreign_keys=document_id)
    position = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    if snorkel_postgres:
        words = Column(postgresql.ARRAY(String), nullable=False)
        char_offsets = Column(postgresql.ARRAY(Integer), nullable=False)
        lemmas = Column(postgresql.ARRAY(String))
        pos_tags = Column(postgresql.ARRAY(String))
        ner_tags = Column(postgresql.ARRAY(String))
        dep_parents = Column(postgresql.ARRAY(Integer))
        dep_labels = Column(postgresql.ARRAY(String))
    else:
        words = Column(PickleType, nullable=False)
        char_offsets = Column(PickleType, nullable=False)
        lemmas = Column(PickleType)
        pos_tags = Column(PickleType)
        ner_tags = Column(PickleType)
        dep_parents = Column(PickleType)
        dep_labels = Column(PickleType)

    __mapper_args__ = {
        'polymorphic_identity': 'sentence',
    }

    __table_args__ = (
        UniqueConstraint(document_id, position),
    )

    def _asdict(self):
        return {
            'id': self.id,
            'document': self.document,
            'position': self.position,
            'text': self.text,
            'words': self.words,
            'char_offsets': self.char_offsets,
            'lemmas': self.lemmas,
            'pos_tags': self.pos_tags,
            'ner_tags': self.ner_tags,
            'dep_parents': self.dep_parents,
            'dep_labels': self.dep_labels
        }

    def __repr__(self):
        return "Sentence" + unicode((self.document, self.position, self.text))


class Table(Context):
    """A table Context in a Document."""
    __tablename__ = 'table'
    id = Column(Integer, ForeignKey('context.id'), primary_key=True)
    document_id = Column(Integer, ForeignKey('document.id'))
    document = relationship('Document', backref=backref('tables', cascade='all, delete-orphan'), foreign_keys=document_id)
    position = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)

    __mapper_args__ = {
        'polymorphic_identity': 'table',
    }

    __table_args__ = (
        UniqueConstraint(document_id, position),
    )

    def __repr__(self):
        return "Table(Doc: %s, Position: %s)" % (self.document.name, self.position)


class Row(Context):
    """A row Context in a Document."""
    __tablename__ = 'row'
    id = Column(Integer, ForeignKey('context.id'), primary_key=True)
    document_id = Column(Integer, ForeignKey('document.id'))
    table_id = Column(Integer, ForeignKey('table.id'))
    document = relationship('Document', backref=backref('rows', cascade='all, delete-orphan'), foreign_keys=document_id)
    table = relationship('Table', backref=backref('rows', cascade='all, delete-orphan'), foreign_keys=table_id)
    position = Column(Integer, nullable=False)

    __mapper_args__ = {
        'polymorphic_identity': 'row',
    }

    __table_args__ = (
        UniqueConstraint(document_id, table_id, position),
    )

    def __repr__(self):
        return "Row(Doc: %s, Table: %s, Position: %s)" % (self.document.name, self.table.position, self.position)


class Col(Context):
    """A column Context in a Document."""
    __tablename__ = 'col'
    id = Column(Integer, ForeignKey('context.id'), primary_key=True)
    document_id = Column(Integer, ForeignKey('document.id'))
    table_id = Column(Integer, ForeignKey('table.id'))
    document = relationship('Document', backref=backref('cols', cascade='all, delete-orphan'), foreign_keys=document_id)
    table = relationship('Table', backref=backref('cols', cascade='all, delete-orphan'), foreign_keys=table_id)
    position = Column(Integer, nullable=False)

    __mapper_args__ = {
        'polymorphic_identity': 'col',
    }

    __table_args__ = (
        UniqueConstraint(document_id, table_id, position),
    )

    def __repr__(self):
        return "Col(Doc: %s, Table: %s, Position: %s)" % (self.document.name, self.table.position, self.position)


class Cell(Context):
    """A cell Context in a Document."""
    __tablename__ = 'cell'
    id = Column(Integer, ForeignKey('context.id'), primary_key=True)
    document_id = Column(Integer, ForeignKey('document.id'))
    table_id = Column(Integer, ForeignKey('table.id'))
    row_id =  Column(Integer, ForeignKey('row.id'))
    col_id =  Column(Integer, ForeignKey('col.id'))
    document = relationship('Document', backref=backref('cells', cascade='all, delete-orphan'), foreign_keys=document_id)
    table = relationship('Table', backref=backref('cells', cascade='all, delete-orphan'), foreign_keys=table_id)
    row = relationship('Row', backref=backref('cells', cascade='all, delete-orphan'), foreign_keys=row_id)
    col = relationship('Col', backref=backref('cells', cascade='all, delete-orphan'), foreign_keys=col_id)
    row_num = Column(Integer)
    col_num = Column(Integer)
    text = Column(Text, nullable=False)
    html_tag = Column(Text)
    if snorkel_postgres:
        html_attrs = Column(postgresql.ARRAY(String))
        html_anc_tags = Column(postgresql.ARRAY(String))
        html_anc_attrs = Column(postgresql.ARRAY(String))
    else:
        html_attrs = Column(PickleType)
        html_anc_tags = Column(PickleType)
        html_anc_attrs = Column(PickleType)

    __mapper_args__ = {
        'polymorphic_identity': 'cell',
    }

    __table_args__ = (
        UniqueConstraint(document_id, table_id, row_id, col_id),
    )

    def __repr__(self):
        return ("Cell(Doc: %s, Table: %s, Row: %s, Col: %s)" % 
            (self.document.name, self.table.position, self.row.position, self.col.position))


class Phrase(Context):
    """A phrase Context in a Document."""
    __tablename__ = 'phrase'
    id = Column(Integer, ForeignKey('context.id'), primary_key=True)
    document_id = Column(Integer, ForeignKey('document.id'))
    table_id = Column(Integer, ForeignKey('table.id'))
    row_id =  Column(Integer, ForeignKey('row.id'))
    col_id =  Column(Integer, ForeignKey('col.id'))
    cell_id = Column(Integer, ForeignKey('cell.id'))
    phrase_id = Column(Integer, nullable=False)
    document = relationship('Document', backref=backref('phrases', cascade='all, delete-orphan'), foreign_keys=document_id)
    table = relationship('Table', backref=backref('phrases', cascade='all, delete-orphan'), foreign_keys=table_id)
    cell = relationship('Cell', backref=backref('phrases', cascade='all, delete-orphan'), foreign_keys=cell_id)
    row = relationship('Row', backref=backref('phrases', cascade='all, delete-orphan'), foreign_keys=row_id)
    col = relationship('Col', backref=backref('phrases', cascade='all, delete-orphan'), foreign_keys=col_id)
    position = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    row_num = Column(Integer)
    col_num = Column(Integer)
    html_tag = Column(Text)
    if snorkel_postgres:
        html_attrs = Column(postgresql.ARRAY(String))
        html_anc_tags = Column(postgresql.ARRAY(String))
        html_anc_attrs = Column(postgresql.ARRAY(String))
        words = Column(postgresql.ARRAY(String), nullable=False)
        char_offsets = Column(postgresql.ARRAY(Integer), nullable=False)
        lemmas = Column(postgresql.ARRAY(String))
        pos_tags = Column(postgresql.ARRAY(String))
        ner_tags = Column(postgresql.ARRAY(String))
        dep_parents = Column(postgresql.ARRAY(Integer))
        dep_labels = Column(postgresql.ARRAY(String))
    else:
        html_attrs = Column(PickleType)
        html_anc_tags = Column(PickleType)
        html_anc_attrs = Column(PickleType)
        words = Column(PickleType, nullable=False)
        char_offsets = Column(PickleType, nullable=False)
        lemmas = Column(PickleType)
        pos_tags = Column(PickleType)
        ner_tags = Column(PickleType)
        dep_parents = Column(PickleType)
        dep_labels = Column(PickleType)

    __mapper_args__ = {
        'polymorphic_identity': 'phrase',
    }

    __table_args__ = (
        UniqueConstraint(document_id, phrase_id),
    )

    def _asdict(self):
        return {
            'id': self.id,
            'document': self.document,
            'phrase_id': self.phrase_id,
            'position': self.position,
            'text': self.text,
            'row_num': self.row_num,
            'col_num': self.col_num,
            'html_tag': self.html_tag,
            'html_attrs': self.html_attrs,
            'html_anc_tags': self.html_anc_tags,
            'html_anc_attrs': self.html_anc_attrs,
            'words': self.words,
            'char_offsets': self.char_offsets,
            'lemmas': self.lemmas,
            'pos_tags': self.pos_tags,
            'ner_tags': self.ner_tags,
            'dep_parents': self.dep_parents,
            'dep_labels': self.dep_labels
        }

    def __repr__(self):
            return ("Phrase(Doc: %s, Table: %s, Row: %s, Col: %s, Position: %s, Text: %s)" % 
                (self.document.name,
                getattr(self.table, 'position', 'X'), 
                getattr(self.row, 'position', 'X'), 
                getattr(self.col, 'position', 'X'), 
                self.position, 
                self.text))

class TemporaryContext(object):
    """
    A context which does not incur the overhead of a proper ORM-based Context object.
    The TemporaryContext class is specifically for the candidate extraction process, during which a CandidateSpace
    object will generate many TemporaryContexts, which will then be filtered by Matchers prior to materialization
    of Candidates and constituent Context objects.

    Every Context object has a corresponding TemporaryContext object from which it inherits.

    A TemporaryContext must have specified equality / set membership semantics, a stable_id for checking
    uniqueness against the database, and a corresponding Context object.
    """
    def __init__(self):
        self.id = None

    def load_id_or_insert(self, session):
        if self.id is None:
            stable_id = self.get_stable_id()
            id = session.execute(select([Context.id]).where(Context.stable_id == stable_id)).first()
            if id is None:
                self.id = session.execute(
                        Context.__table__.insert(),
                        {'type': self._get_table_name(), 'stable_id': stable_id}).inserted_primary_key[0]
                insert_args = self._get_insert_args()
                insert_args['id'] = self.id
                for (key, val) in insert_args.items():
                    if isinstance(val, list):
                        if snorkel_postgres:
                            raise NotImplementedError
                        else:
                            insert_args[key] = pickle.dumps(val)
                session.execute(text(self._get_insert_query()), insert_args)
            else:
                self.id = id[0]

    def __eq__(self, other):
        raise NotImplementedError()

    def __ne__(self, other):
        raise NotImplementedError()

    def __hash__(self):
        raise NotImplementedError()

    def _get_polymorphic_identity(self):
        raise NotImplementedError()

    def get_stable_id(self):
        raise NotImplementedError()

    def _get_table_name(self):
        raise NotImplementedError()

    def _get_insert_query(self):
        raise NotImplementedError()

    def _get_insert_args(self):
        raise NotImplementedError()


class TemporarySpan(TemporaryContext):
    """The TemporaryContext version of Span"""
    def __init__(self, parent, char_start, char_end, meta=None):
        super(TemporarySpan, self).__init__()
        self.parent     = parent  # The parent Context of the Span
        self.char_end   = char_end
        self.char_start = char_start
        self.meta       = meta

    def __len__(self):
        return self.char_end - self.char_start + 1

    def __eq__(self, other):
        try:
            # TODO: add check that other is not an ImpliciSpan
            return (self.parent == other.parent and 
                    self.char_start == other.char_start and 
                    self.char_end == other.char_end)
        except AttributeError:
            return False

    def __ne__(self, other):
        try:
            # TODO: add check that other is not an ImpliciSpan
            return (self.parent != other.parent or 
                    self.char_start != other.char_start or 
                    self.char_end != other.char_end)
        except AttributeError:
            return True

    def __hash__(self):
        return hash(self.parent) + hash(self.char_start) + hash(self.char_end)

    def get_stable_id(self):
        # return construct_stable_id(self.parent, self._get_polymorphic_identity(), self.char_start, self.char_end)
        return "%s::%s:%s:%s:%s" % (
            self.parent.document.name, 
            self._get_polymorphic_identity(), 
            self.parent.id, 
            self.char_start,
            self.char_end)

    def _get_table_name(self):
        return 'span'

    def _get_polymorphic_identity(self):
        return 'span'

    def _get_insert_query(self):
        return """INSERT INTO span VALUES(:id, :parent_id, :char_start, :char_end, :meta)"""

    def _get_insert_args(self):
        return {'parent_id' : self.parent.id,
                'char_start': self.char_start,
                'char_end'  : self.char_end,
                'meta'      : self.meta}

    def get_word_start(self):
        return self.char_to_word_index(self.char_start)

    def get_word_end(self):
        return self.char_to_word_index(self.char_end)

    def get_n(self):
        return self.get_word_end() - self.get_word_start() + 1

    def char_to_word_index(self, ci):
        """Given a character-level index (offset), return the index of the **word this char is in**"""
        i = None
        for i, co in enumerate(self.parent.char_offsets):
            if ci == co:
                return i
            elif ci < co:
                return i-1
        return i

    def word_to_char_index(self, wi):
        """Given a word-level index, return the character-level index (offset) of the word's start"""
        return self.parent.char_offsets[wi]

    def get_attrib_tokens(self, a='words'):
        """Get the tokens of sentence attribute _a_ over the range defined by word_offset, n"""
        return self.parent.__getattribute__(a)[self.get_word_start():self.get_word_end() + 1]

    def get_attrib_span(self, a, sep=" "):
        """Get the span of sentence attribute _a_ over the range defined by word_offset, n"""
        # NOTE: Special behavior for words currently (due to correspondence with char_offsets)
        if a == 'words':
            return self.parent.text[self.char_start:self.char_end + 1]
        else:
            return sep.join(self.get_attrib_tokens(a))

    def get_span(self, sep=" "):
        return self.get_attrib_span('words', sep)

    def __contains__(self, other_span):
        return (self.parent == other_span.parent 
            and other_span.char_start >= self.char_start 
            and other_span.char_end <= self.char_end)

    def __getitem__(self, key):
        """
        Slice operation returns a new candidate sliced according to **char index**
        Note that the slicing is w.r.t. the candidate range (not the abs. sentence char indexing)
        """
        if isinstance(key, slice):
            char_start = self.char_start if key.start is None else self.char_start + key.start
            if key.stop is None:
                char_end = self.char_end
            elif key.stop >= 0:
                char_end = self.char_start + key.stop - 1
            else:
                char_end = self.char_end + key.stop
            return self._get_instance(char_start=char_start, char_end=char_end, parent=self.parent)
        else:
            raise NotImplementedError()

    def __repr__(self):
        return u'%s("%s", parent=%s, chars=[%s,%s], words=[%s,%s])' \
            % (self.__class__.__name__, self.get_span(), self.parent.id, self.char_start, self.char_end,
               self.get_word_start(), self.get_word_end())

    def _get_instance(self, **kwargs):
        return TemporarySpan(**kwargs)


class Span(Context, TemporarySpan):
    """
    A span of characters, identified by Context id and character-index start, end (inclusive).

    char_offsets are **relative to the Context start**
    """
    __tablename__ = 'span'
    id = Column(Integer, ForeignKey('context.id'), primary_key=True)
    parent_id = Column(Integer, ForeignKey('context.id'))
    char_start = Column(Integer, nullable=False)
    char_end = Column(Integer, nullable=False)
    meta = Column(PickleType)

    __table_args__ = (
        UniqueConstraint(parent_id, char_start, char_end),
    )

    __mapper_args__ = {
        'polymorphic_identity': 'span',
        'inherit_condition': (id == Context.id)
    }

    parent = relationship('Context', backref=backref('spans', cascade='all, delete-orphan'), foreign_keys=parent_id)

    def _get_instance(self, **kwargs):
        return Span(**kwargs)

    # We redefine these to use default semantics, overriding the operators inherited from TemporarySpan
    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        return self is not other

    def __hash__(self):
        return id(self)


class TemporaryImplicitSpan(TemporarySpan):
    """The TemporaryContext version of ImplicitSpan"""
    def __init__(self, parent, char_start, char_end, expander_key, position, 
            text, words, char_offsets, lemmas, pos_tags, ner_tags, dep_parents,
            dep_labels, meta=None):
        super(TemporarySpan, self).__init__()
        self.parent         = parent  # The parent Context of the Span
        self.char_start     = char_start
        self.char_end       = char_end
        self.expander_key   = expander_key
        self.position       = position
        self.text           = text
        self.words          = words
        self.char_offsets   = char_offsets
        self.lemmas         = lemmas
        self.pos_tags       = pos_tags
        self.ner_tags       = ner_tags
        self.dep_parents    = dep_parents
        self.dep_labels     = dep_labels
        self.meta           = meta

    def __len__(self):
        return sum(map(len, words))

    def __eq__(self, other):
        try:
            return (self.parent == other.parent and
                    self.char_start == other.char_start and 
                    self.char_end == other.char_end and
                    self.expander_key == other.expander_key and 
                    self.position == other.position)
        except AttributeError:
            return False

    def __ne__(self, other):
        try:
            return (self.parent != other.parent or
                    self.char_start != other.char_start or 
                    self.char_end != other.char_end or 
                    self.expander_key != other.expander_key or 
                    self.position != other.position)
        except AttributeError:
            return True

    def __hash__(self):
        return (hash(self.parent) + hash(self.char_start) + hash(self.char_end) 
                + hash(self.expander_key) + hash(self.position))

    def get_stable_id(self):
        # return (construct_stable_id(self.parent, self._get_polymorphic_identity(), self.char_start, self.char_end)
        #     + ':%s:%s' % (self.expander_key, self.position))
        return '%s::%s:%s:%s:%s:%s:%s' % (
            self.parent.document.name, 
            self._get_polymorphic_identity(),                             
            self.parent.id, 
            self.char_start, 
            self.char_end, 
            self.expander_key, 
            self.position)

    def _get_table_name(self):
        return 'implicit_span'

    def _get_polymorphic_identity(self):
        return 'implicit_span'

    def _get_insert_query(self):
        return """INSERT INTO implicit_span VALUES(:id, :parent_id, :char_start, :char_end, :expander_key, :position, :text, :words, :char_offsets, :lemmas, :pos_tags, :ner_tags, :dep_parents, :dep_labels, :meta)"""

    def _get_insert_args(self):
        return {'parent_id'     : self.parent.id,
                'char_start'    : self.char_start,
                'char_end'      : self.char_end,
                'expander_key'  : self.expander_key,
                'position'      : self.position,
                'text'          : self.text,
                'words'         : self.words,
                'char_offsets'  : self.char_offsets,
                'lemmas'        : self.lemmas,
                'pos_tags'      : self.pos_tags,
                'ner_tags'      : self.ner_tags,
                'dep_parents'   : self.dep_parents,
                'dep_labels'    : self.dep_labels,
                'meta'          : self.meta
                }

    def get_n(self):
        return len(self.words)

    def char_to_word_index(self, ci):
        """Given a character-level index (offset), return the index of the **word this char is in**"""
        i = None
        for i, co in enumerate(self.char_offsets):
            if ci == co:
                return i
            elif ci < co:
                return i-1
        return i

    def word_to_char_index(self, wi):
        """Given a word-level index, return the character-level index (offset) of the word's start"""
        return self.char_offsets[wi]

    def get_attrib_tokens(self, a='words'):
        """Get the tokens of sentence attribute _a_ over the range defined by word_offset, n"""
        return self.__getattribute__(a)[self.get_word_start():self.get_word_end() + 1]

    def get_attrib_span(self, a, sep=" "):
        """Get the span of sentence attribute _a_ over the range defined by word_offset, n"""
        # NOTE: Special behavior for words currently (due to correspondence with char_offsets)
        if a == 'words':
            return self.text
        else:
            return sep.join(self.get_attrib_tokens(a))

    def __getitem__(self, key):
        """
        Slice operation returns a new candidate sliced according to **char index**
        Note that the slicing is w.r.t. the candidate range (not the abs. sentence char indexing)
        """
        if isinstance(key, slice):
            char_start = self.char_start if key.start is None else self.char_start + key.start
            if key.stop is None:
                char_end = self.char_end
            elif key.stop >= 0:
                char_end = self.char_start + key.stop - 1
            else:
                char_end = self.char_end + key.stop
            return self._get_instance(parent=self.parent, char_start=char_start, char_end=char_end, expander_key=expander_key,
                position=position, text=text, words=words, char_offsets=char_offsets, lemmas=lemmas, pos_tags=pos_tags, 
                ner_tags=ner_tags, dep_parents=dep_parents, dep_labels=dep_labels, meta=meta)
        else:
            raise NotImplementedError()

    def __repr__(self):
        return '%s("%s", parent=%s, words=[%s,%s], position=[%s])' \
            % (self.__class__.__name__, self.get_span(), self.parent.id, 
               self.get_word_start(), self.get_word_end(), self.position)

    def _get_instance(self, **kwargs):
        return TemporaryImplicitSpan(**kwargs)


class ImplicitSpan(Context, TemporaryImplicitSpan):
    """
    A span of characters that may not have appeared verbatim in the source text.
    It is identified by Context id, character-index start and end (inclusive), 
    as well as a key representing what 'expander' function drew the ImplicitSpan 
    from an  existing Span, and a position (where position=0 corresponds to the 
    first ImplicitSpan produced from the expander function).

    The character-index start and end point to the segment of text that was
    expanded to produce the ImplicitSpan.
    """
    __tablename__ = 'implicit_span'
    id = Column(Integer, ForeignKey('context.id'), primary_key=True)
    parent_id = Column(Integer, ForeignKey('context.id'))
    char_start = Column(Integer, nullable=False)
    char_end = Column(Integer, nullable=False)
    expander_key = Column(String, nullable=False)
    position = Column(Integer, nullable=False)
    text = Column(String)
    if snorkel_postgres:
        words = Column(postgresql.ARRAY(String), nullable=False)
        char_offsets = Column(postgresql.ARRAY(Integer), nullable=False)
        lemmas = Column(postgresql.ARRAY(String))
        pos_tags = Column(postgresql.ARRAY(String))
        ner_tags = Column(postgresql.ARRAY(String))
        dep_parents = Column(postgresql.ARRAY(Integer))
        dep_labels = Column(postgresql.ARRAY(String))
    else:
        words = Column(PickleType, nullable=False)
        char_offsets = Column(PickleType, nullable=False)
        lemmas = Column(PickleType)
        pos_tags = Column(PickleType)
        ner_tags = Column(PickleType)
        dep_parents = Column(PickleType)
        dep_labels = Column(PickleType)
    meta = Column(PickleType)

    __table_args__ = (
        UniqueConstraint(parent_id, char_start, char_end, expander_key, position),
    )

    __mapper_args__ = {
        'polymorphic_identity': 'implicit_span',
        'inherit_condition': (id == Context.id)
    }

    parent = relationship('Context', backref=backref('implicit_spans', cascade='all, delete-orphan'), foreign_keys=parent_id)

    def _get_instance(self, **kwargs):
        return ImplicitSpan(**kwargs)

    # We redefine these to use default semantics, overriding the operators inherited from TemporarySpan
    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        return self is not other

    def __hash__(self):
        return id(self)


def split_stable_id(stable_id):
    """
    Split stable id, returning:
        * Parent (root) stable ID
        * Context polymorphic type
        * Character offset start, end *relative to parent start*
    Returns tuple of four values.
    """
    split1 = stable_id.split('::')
    if len(split1) == 2:
        split2 = split1[1].split(':')
        if len(split2) == 3:
            return split1[0], split2[0], int(split2[1]), int(split2[2])
    raise ValueError("Malformed stable_id:", stable_id)


def construct_stable_id(parent_context, polymorphic_type, relative_char_offset_start, relative_char_offset_end):
    """Contruct a stable ID for a Context given its parent and its character offsets relative to the parent"""
    parent_id, _, parent_char_start, _ = split_stable_id(parent_context.stable_id)
    start = parent_char_start + relative_char_offset_start
    end   = parent_char_start + relative_char_offset_end
    return "%s::%s:%s:%s" % (parent_id, polymorphic_type, start, end)
