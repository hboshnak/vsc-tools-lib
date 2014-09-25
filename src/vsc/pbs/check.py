#!/usr/bin/env python

import sqlite3
from vsc.utils import bytes2size
from vsc.event_logger import EventLogger

class JobChecker(EventLogger):
    '''Semantic checker for jobs'''

    def __init__(self, db_name):
        '''Constructor for job checker'''
        super(JobChecker, self).__init__()
        self._conn = sqlite3.connect(db_name)
        self._cursor = self._conn.cursor()

    def check(self, job):
        '''Check semantics of given job'''
        self.check_pmem(job)

    def check_pmem(self, job):
        '''Check whether the requested memory per node is available'''
        ppn = job.resource_spec('ppn')
        pmem = job.resource_spec('pmem')
        print ppn, pmem
        if ppn and pmem:
            node_mem = ppn*pmem
        else:
            return True
        mem_sizes = self._mem_sizes(job.resource_spec('partition')).keys()
        for mem in mem_sizes:
            if node_mem < mem:
                return True
        self.reg_event('insufficient_node_mem',
                       {'mem': bytes2size(node_mem, 'gb')})

    def _mem_sizes(self, partition):
        '''retrieve the memory sizes of the nodes from the databse'''
        sizes = {}
        stmt = '''SELECT n.mem, count(n.node_id)
                      FROM nodes as n NATURAL JOIN partitions as p
                      WHERE p.partition_name = ?
                      GROUP BY mem'''
        self._cursor.execute(stmt, (partition, ))
        for row in self._cursor:
            sizes[row[0]] = row[1]
        return sizes

