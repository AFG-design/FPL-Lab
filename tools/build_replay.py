#!/usr/bin/env python3
"""FL-128: run build.py with every download recorded, or replayed from a recording, and the clock frozen, so two
versions of the build can be checked for identical output.

    # 1. record one real build (network on) into CACHE, from a copy of the repo
    python3 tools/build_replay.py record CACHE --repo DIR -- 8122679 site/data.json
    # 2. replay into two copies at the same commit's data (one per build version), then diff the copies
    python3 tools/build_replay.py replay CACHE --repo OLD --now 2026-11-14T12:00:00+00:00 -- 8122679 site/data.json
    python3 tools/build_replay.py replay CACHE --repo NEW --now 2026-11-14T12:00:00+00:00 -- 8122679 site/data.json
    diff -r --exclude=.git --exclude=__pycache__ OLD NEW

What it fixes so two runs can be compared:
  - every urllib.request.urlopen call (FPL API, badges, anything else) is saved by method + URL + body in record mode
    and served from the recording in replay mode. A request missing from the recording fails loudly (no network
    fallback), so a build that fetched something new is never silently compared on different data.
  - datetime.datetime.now / utcnow / today and datetime.date.today return --now (record mode too, when given).
  - in replay, time.sleep does nothing (get()'s retry waits) and meta.build_secs (wall-clock) is set to 0 in the
    output, the one field that can't be frozen without changing how the build times itself.
Errors are recorded as well (HTTP status or connection error) and raised again in replay, so a failing source takes
the same fallback path both times.
"""
import argparse, datetime, hashlib, io, json, os, runpy, sys, time, urllib.error, urllib.request

_real_urlopen = urllib.request.urlopen


def _key(req):
    url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
    method = req.get_method() if isinstance(req, urllib.request.Request) else "GET"
    data = req.data if isinstance(req, urllib.request.Request) else None
    h = hashlib.sha256(f"{method} {url}".encode() + (data or b"")).hexdigest()[:24]
    return h, url


class _Resp(io.BytesIO):
    def __init__(self, body, status=200, headers=None, url=""):
        super().__init__(body)
        self.status, self.code, self.headers, self.url = status, status, headers or {}, url

    def getcode(self):
        return self.status

    def geturl(self):
        return self.url

    def info(self):
        return self.headers


def _recorder(cache):
    def urlopen(req, *a, **kw):
        h, url = _key(req)
        meta = {"url": url}
        try:
            with _real_urlopen(req, *a, **kw) as r:
                body = r.read()
                meta.update(status=getattr(r, "status", 200), headers=dict(r.headers.items()))
        except urllib.error.HTTPError as ex:
            meta.update(error="http", code=ex.code, msg=str(ex.reason))
            json.dump(meta, open(os.path.join(cache, h + ".json"), "w"))
            raise
        except Exception as ex:
            meta.update(error="url", msg=f"{type(ex).__name__}: {ex}")
            json.dump(meta, open(os.path.join(cache, h + ".json"), "w"))
            raise
        open(os.path.join(cache, h + ".body"), "wb").write(body)
        json.dump(meta, open(os.path.join(cache, h + ".json"), "w"))
        return _Resp(body, meta["status"], meta["headers"], url)
    return urlopen


def _player(cache):
    def urlopen(req, *a, **kw):
        h, url = _key(req)
        mp = os.path.join(cache, h + ".json")
        if not os.path.exists(mp):
            raise RuntimeError(f"build_replay: {url} is not in the recording {cache}; record again")
        meta = json.load(open(mp))
        if meta.get("error") == "http":
            raise urllib.error.HTTPError(url, meta["code"], meta["msg"], {}, None)
        if meta.get("error"):
            raise urllib.error.URLError(meta["msg"])
        return _Resp(open(os.path.join(cache, h + ".body"), "rb").read(), meta["status"], meta["headers"], url)
    return urlopen


def freeze(now):
    """datetime.datetime / datetime.date with now() and today() pinned to `now` (an aware datetime)."""
    real_dt, real_date = datetime.datetime, datetime.date

    class FrozenDateTime(real_dt):
        @classmethod
        def now(cls, tz=None):
            v = now.astimezone(tz) if tz else now.astimezone().replace(tzinfo=None)
            return cls.combine(v.date(), v.timetz() if tz else v.time())

        @classmethod
        def utcnow(cls):
            v = now.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            return cls.combine(v.date(), v.time())

        @classmethod
        def today(cls):
            return cls.now()

    class FrozenDate(real_date):
        @classmethod
        def today(cls):
            d = now.astimezone().date()
            return cls(d.year, d.month, d.day)

    datetime.datetime, datetime.date = FrozenDateTime, FrozenDate


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("record", "replay"))
    ap.add_argument("cache")
    ap.add_argument("--repo", required=True, help="the repo copy whose build.py runs, and whose files it writes")
    ap.add_argument("--now", help="ISO time with offset to pin the clock to (needed for replay)")
    argv = sys.argv[1:]
    cut = argv.index("--") if "--" in argv else len(argv)
    a, args = ap.parse_args(argv[:cut]), argv[cut + 1:]   # build.py's own arguments come after --
    if a.mode == "replay" and not a.now:
        sys.exit("build_replay: replay needs --now so both builds see the same clock")
    a.cache = os.path.abspath(a.cache)   # the build runs from the repo copy's folder
    os.makedirs(a.cache, exist_ok=True)
    if a.now:
        now = datetime.datetime.fromisoformat(a.now)
        if now.tzinfo is None:
            sys.exit("build_replay: --now needs a UTC offset, e.g. 2026-11-14T12:00:00+00:00")
        freeze(now)
    urllib.request.urlopen = _recorder(a.cache) if a.mode == "record" else _player(a.cache)
    if a.mode == "replay":
        time.sleep = lambda s: None
    repo = os.path.abspath(a.repo)
    os.chdir(repo)
    sys.path.insert(0, repo)
    sys.argv = ["build.py", *args]
    runpy.run_path(os.path.join(repo, "build.py"), run_name="__main__")
    if a.mode == "replay":
        out = args[1] if len(args) > 1 else "data.json"
        d = json.load(open(out))
        d["meta"]["build_secs"] = 0
        json.dump(d, open(out, "w"), separators=(",", ":"))


if __name__ == "__main__":
    main()
