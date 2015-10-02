from uuid import uuid4
from itertools import cycle

from pyrsistent import PClass, field

from twisted.web.client import ResponseFailed

from twisted.internet.defer import maybeDeferred

from flocker.testtools import loop_until

# XXX A value I think works on both Cinder and EBS, and the
# docs recommend against passing None; no other purpose here.
MAXIMUM_SIZE = 100 * 2 ** 30


def _report_ssl_error(failure):
    failure.trap(ResponseFailed)
    for reason in failure.value.reasons:
        reason.printTraceback()
    return reason


class _ReadRequest(PClass):
    """
    
    """
    client = field(mandatory=True)

    def run(self):
        d = self.client.list_datasets_state()
        d.addErrback(_report_ssl_error)
        return d


class _WriteRequest(PClass):
    client = field(mandatory=True)
    dataset_id = field(mandatory=True)
    some_primaries = field(mandatory=True)

    @classmethod
    def from_client(cls, client):
        some_primaries = iter(cycle([uuid4(), uuid4()]))
        d = client.list_datasets_configuration()
        def create(datasets):
            for a_dataset in datasets:
                return _WriteRequest(
                    client=client,
                    dataset_id=a_dataset.dataset_id,
                    some_primaries=some_primaries,
                )
            # If necessary, configure a dataset.
            dataset_id = uuid4()
            d = client.create_dataset(
                primary=next(some_primaries),
                dataset_id=dataset_id,
                maximum_size=MAXIMUM_SIZE,
            )
            return d.addCallback(
                lambda ignored: cls.from_client(client)
            )
        d.addCallback(create)
        return d

    def run(self):
        return self.client.move_dataset(
            primary=next(self.some_primaries),
            dataset_id=self.dataset_id,
        )


@classmethod
def pick_primary_node(cls, client):
    d = client.list_nodes()
    def pick_primary(nodes):
        for node in nodes:
            return cls(client=client, primary=node)
        # Cannot proceed if there are no nodes in the cluster!
        raise Exception("Found no cluster nodes; can never converge.")
    d.addCallback(pick_primary)
    return d


class _CreateDatasetConvergence(PClass):
    client = field(mandatory=True)
    primary = field(mandatory=True)

    # XXX Leaks datasets!  Alters cluster state so likely alters its own future
    # results.  Need a cleanup stage for metrics.

    from_client = pick_primary_node

    def run(self):
        def dataset_matches(expected, inspecting):
            return (
                inspecting.dataset_id == inspecting.dataset_id and
                inspecting.primary == inspecting.primary
            )

        d = self.client.create_dataset(
            primary=self.primary.uuid,
            maximum_size=MAXIMUM_SIZE,
        )
        d.addCallback(
            loop_until_converged,
            self.client.list_datasets_state,
            dataset_matches,
        )
        return d


class _CreateContainerConvergence(PClass):
    # XXX Should involve a dataset, does not; probably does not make much real
    # difference.
    client = field(mandatory=True)
    primary = field(mandatory=True)

    from_client = pick_primary_node

    def run(self):
        def container_matches(expected, inspecting):
            return expected.serialize() == inspecting.serialize()

        d = self.client.create_container(
            self.primary,
            unicode(uuid4()),
            u"nginx",
        )
        d.addCallback(
            loop_until_converged,
            self.client.list_containers_state,
            container_matches,
        )
        return d


def _converged(expected, list_state, state_matches):
    d = list_state()

    def find_match(existing_state):
        return any(
            state_matches(state, expected)
            for state in existing_state
        )
    d.addCallback(find_match)
    return d

def loop_until_converged(expected, list_state, state_matches):
    # XXX reactor
    return loop_until(
        lambda: _converged(expected, list_state, state_matches)
    )


_metrics = {
    "read-request": _ReadRequest,
    "write-request": _WriteRequest.from_client,
    "create-dataset-convergence": _CreateDatasetConvergence.from_client,
    "create-container-convergence": _CreateContainerConvergence.from_client,
}


def get_metric(client, name):
    return maybeDeferred(_metrics[name], client=client)