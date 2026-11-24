import sfdispatch


class BoomFeed:
    calls = []
    status, data_age = "LIVE", None

    def poll(self):
        raise ValueError("bad row")


def test_step_survives_feed_error():
    f = sfdispatch.Fetcher(feed=BoomFeed(), clock=lambda: 100.0)
    f.step()                     # must not raise
    _, _, status, _ = f.take()
    assert status == "OFFLINE"


def test_watchdog_reports_offline_when_fetcher_silent():
    t = [100.0]
    f = sfdispatch.Fetcher(feed=BoomFeed(), clock=lambda: t[0])
    f.status = "LIVE"
    f.last_report = 100.0
    t[0] = 100.0 + 3 * sfdispatch.POLL_S + 1
    assert f.take()[2] == "OFFLINE"
