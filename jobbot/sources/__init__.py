from . import adzuna, ats, remote

# name -> fetch(settings, profile, companies) -> list[Job]
REGISTRY = {
    "greenhouse": ats.fetch_greenhouse,
    "lever": ats.fetch_lever,
    "ashby": ats.fetch_ashby,
    "adzuna": adzuna.fetch,
    "remoteok": remote.fetch_remoteok,
    "remotive": remote.fetch_remotive,
}
