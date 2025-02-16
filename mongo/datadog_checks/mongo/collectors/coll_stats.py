# (C) Datadog, Inc. 2020-present
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

from six import iteritems

from datadog_checks.base import AgentCheck
from datadog_checks.mongo.collectors.base import MongoCollector
from datadog_checks.mongo.metrics import COLLECTION_METRICS


class CollStatsCollector(MongoCollector):
    """Collects metrics from the 'collstats' command.
    Note: Collecting those metrics requires that 'collection' is set in the 'additional_metrics' section of the config.
    """

    def __init__(self, check, db_name, tags, coll_names=None):
        super(CollStatsCollector, self).__init__(check, tags)
        self.coll_names = coll_names
        self.db_name = db_name

    def compatible_with(self, deployment):
        # Can only be run once per cluster.
        return deployment.is_principal()

    def _get_collections(self, api):
        if self.coll_names:
            return self.coll_names
        return api.list_authorized_collections(self.db_name)

    def collect(self, api):
        coll_names = self._get_collections(api)
        for coll_name in coll_names:
            # Grab the stats from the collection
            for coll_stats in api.coll_stats(self.db_name, coll_name):
                # Submit the metrics
                storage_stats = coll_stats.get('storageStats', {})
                latency_stats = coll_stats.get('latencyStats', {})
                query_stats = coll_stats.get('queryExecStats', {})
                payload = {'collection': {**storage_stats, **latency_stats, **query_stats}}
                additional_tags = ["db:%s" % self.db_name, "collection:%s" % coll_name]
                if coll_stats.get('shard'):
                    # If the collection is sharded, add the shard tag
                    additional_tags.append("shard:%s" % coll_stats['shard'])
                self._submit_payload(payload, additional_tags, COLLECTION_METRICS)

                # Submit the indexSizes metrics manually
                index_sizes = storage_stats.get('indexSizes', {})
                metric_name_alias = self._normalize("collection.indexSizes", AgentCheck.gauge)
                for idx, val in iteritems(index_sizes):
                    # we tag the index
                    idx_tags = self.base_tags + additional_tags + ["index:%s" % idx]
                    self.gauge(metric_name_alias, val, tags=idx_tags)
