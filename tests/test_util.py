import functools
import hashlib
import hmac

try:
    import unittest2 as unittest
except ImportError:
    import unittest

from base64 import b64encode
from datetime import date, time, datetime, timedelta

import testconfig

from geoalchemy import GeometryColumn, Point, WKTSpatialElement, GeometryDDL
from sqlalchemy import Column, Integer, Date, DateTime, Time, Interval, \
    engine_from_config
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base

from blueberrypy.util import CSRFToken, pad_block_cipher_message, \
    unpad_block_cipher_message, from_mapping, to_mapping


engine = engine_from_config(testconfig.config["sqlalchemy_engine"], '')
Session = scoped_session(sessionmaker(engine))

Base = declarative_base()
Base.metadata.bind = engine

# remember to setup postgis
class TestEntity(Base):

    __tablename__ = 'testentity'

    id = Column(Integer, primary_key=True)
    date = Column(Date)
    time = Column(Time)
    datetime = Column(DateTime)
    interval = Column(Interval)
    geo = GeometryColumn(Point(2))

    @property
    def combined(self):
        return datetime.combine(self.date, self.time)

GeometryDDL(TestEntity.__table__)

def orm_session(func):
    def _orm_session(*args, **kwargs):
        session = Session()
        try:
            return func(*args, **kwargs)
        except:
            raise
        finally:
            session.close()
    return functools.update_wrapper(_orm_session, func)


class CSRFTokenTest(unittest.TestCase):

    def test_csrftoken(self):
        csrftoken = CSRFToken("/test", "secret", 1)

        mac = hmac.new("secret", digestmod=hashlib.sha256)
        mac.update("/test")
        mac.update('1')
        testtoken = b64encode(mac.digest())

        self.assertEqual(str(csrftoken), testtoken)
        self.assertTrue(csrftoken.verify(testtoken))

        mac = hmac.new("secret2", digestmod=hashlib.sha256)
        mac.update("/test")
        mac.update('1')
        testtoken = b64encode(mac.digest())

        self.assertNotEqual(str(csrftoken), testtoken)
        self.assertFalse(csrftoken.verify(testtoken))

        mac = hmac.new("secret", digestmod=hashlib.sha256)
        mac.update("/test2")
        mac.update('1')
        testtoken = b64encode(mac.digest())

        self.assertNotEqual(str(csrftoken), testtoken)
        self.assertFalse(csrftoken.verify(testtoken))

        mac = hmac.new("secret", digestmod=hashlib.sha256)
        mac.update("/test2")
        mac.update('2')
        testtoken = b64encode(mac.digest())

        self.assertNotEqual(str(csrftoken), testtoken)
        self.assertFalse(csrftoken.verify(testtoken))


class MappingUtilTest(unittest.TestCase):

    @classmethod
    @orm_session
    def setup_class(cls):
        TestEntity.metadata.create_all(engine)

        te = TestEntity(id=1,
                        date=date(2012, 1, 1),
                        time=time(0, 0, 0),
                        datetime=datetime(2012, 1, 1, 0, 0, 0),
                        interval=timedelta(seconds=3600),
                        geo=WKTSpatialElement("POINT(45.0 45.0)"))

        session = Session()
        session.add(te)
        session.commit()
    setUpClass = setup_class

    @classmethod
    @orm_session
    def teardown_class(cls):
        TestEntity.metadata.drop_all(engine)
    testDownClass = teardown_class

    @orm_session
    def test_to_mapping(self):
        doc = {'date': {'date': '2012-01-01'},
               'time': {'time': '00:00:00'},
               'interval': {'interval': 3600},
               'id': 1,
               'datetime': {'datetime': '2012-01-01T00:00:00'},
               'geo': {'type': 'Point',
                       'coordinates': (45.0, 45.0)}}

        session = Session()
        te = session.query(TestEntity).one()
        result = to_mapping(te)

        self.assertEqual(doc, result)

        serialized_doc = '{"date": {"date": "2012-01-01"}, "datetime": {"datetime": "2012-01-01T00:00:00"}, "geo": {"coordinates": [45.0, 45.0], "type": "Point"}, "id": 1, "interval": {"interval": 3600}, "time": {"time": "00:00:00"}}'
        self.assertEqual(serialized_doc, to_mapping(te, format="json",
                                                    sort_keys=True))

        doc = {'date': {'date': '2012-01-01'},
               'time': {'time': '00:00:00'},
               'datetime': {'datetime': '2012-01-01T00:00:00'},
               'combined': {'datetime': '2012-01-01T00:00:00'},
               'geo': {'type': 'Point', 'coordinates': (45.0, 45.0)}}

        self.assertEqual(doc, to_mapping(te, includes=["combined"],
                                         excludes=["id", "interval"]))

        self.assertEqual("a", to_mapping("a"))
        self.assertEqual(1, to_mapping(1))
        self.assertEqual(1.1, to_mapping(1.1))
        self.assertEqual({'date': '2012-01-01'}, to_mapping(date(2012, 1, 1)))
        self.assertEqual({'time': '00:00:00'}, to_mapping(time(0, 0, 0)))
        self.assertEqual({'interval': 3600}, to_mapping(timedelta(seconds=3600)))
        self.assertEqual({'datetime': '2012-01-01T00:00:00'}, to_mapping(datetime(2012, 1, 1, 0, 0, 0)))
        self.assertEqual({'type': 'Point', 'coordinates': (45.0, 45.0)}, to_mapping(te.geo))

    @orm_session
    def test_from_mapping(self):

        doc = {'date': {'date': '2012-01-01'},
               'time': {'time': '00:00:00'},
               'interval': {'interval': 3600},
               'id': 1,
               'datetime': {'datetime': '2012-01-01T00:00:00'},
               'geo': {'type': 'Point', 'coordinates': (45.0, 45.0)}}

        te = TestEntity()
        te = from_mapping(doc, te)
        self.assertEqual(te.date, date(2012, 1, 1))
        self.assertEqual(te.time, time(0, 0, 0))
        self.assertEqual(te.interval, timedelta(seconds=3600))
        self.assertEqual(te.datetime, datetime(2012, 1, 1, 0, 0, 0))
        self.assertEqual(te.id, 1)
        self.assertEqual(te.geo.geom_wkt, "POINT (45.0000000000000000 45.0000000000000000)")

        te = TestEntity()
        te = from_mapping(doc, te, excludes=["interval"])
        self.assertEqual(te.date, date(2012, 1, 1))
        self.assertEqual(te.time, time(0, 0, 0))
        self.assertIsNone(te.interval)
        self.assertEqual(te.datetime, datetime(2012, 1, 1, 0, 0, 0))
        self.assertEqual(te.id, 1)
        self.assertEqual(te.geo.geom_wkt, "POINT (45.0000000000000000 45.0000000000000000)")

        te = TestEntity()
        json_doc = '{"date": {"date": "2012-01-01"}, "time": {"time": "00:00:00"}, "interval": {"interval": 3600}, "id": 1, "datetime": {"datetime": "2012-01-01T00:00:00"}, "geo": {"coordinates": [45.0, 45.0], "type": "Point"}}'
        te = from_mapping(json_doc, te, format="json")
        self.assertEqual(te.date, date(2012, 1, 1))
        self.assertEqual(te.time, time(0, 0, 0))
        self.assertEqual(te.interval, timedelta(seconds=3600))
        self.assertEqual(te.datetime, datetime(2012, 1, 1, 0, 0, 0))
        self.assertEqual(te.id, 1)
        self.assertEqual(te.geo.geom_wkt, "POINT (45.0000000000000000 45.0000000000000000)")


class BlockCipherPaddingTest(unittest.TestCase):

    def test_pad_block_cipher_message(self):
        padded_message = pad_block_cipher_message("message")
        self.assertEqual(padded_message, "message{{{{{{{{{")

    def test_unpad_block_cipher_message(self):
        self.assertEqual(unpad_block_cipher_message("message{{{{{{{{{"), "message")
