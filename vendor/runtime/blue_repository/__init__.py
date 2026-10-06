"""Optional repositories; nothing is enabled globally at import time."""
from pathlib import Path
from functools import lru_cache
from .api import Repository, RepositoryError

@lru_cache(maxsize=2)
def bundled(profile: str = 'published') -> Repository:
    if profile not in ('published', 'compatible'):
        raise RepositoryError('profile must be published or compatible')
    return Repository.load(Path(__file__).with_name('data') / (profile + '.json'))

@lru_cache(maxsize=2)
def repository_20260921(profile: str = 'compatible') -> Repository:
    """The supplied 1,191-type repository, separately addressed by profile."""
    if profile not in ('published','compatible'):raise RepositoryError('profile must be published or compatible')
    return Repository.load(Path(__file__).with_name('data') / ('repository-20260921-'+profile+'.json'))

@lru_cache(maxsize=1)
def prepared_repository_20260921():
    """Prepared compatible data; the digest is pinned by this package release.

    The compiler and the consumer have no executable-role dependencies. The
    original Repository API remains available as an independent reference path.
    """
    from blue_language.prepared import PreparedRepository
    return PreparedRepository.load(
        Path(__file__).with_name('data') / 'repository-20260921-compatible.prepared.json',
        expected_sha256='07c0b65afa6bf0037f372f0de389eea827896bbee9a39513bf18b5525ec56af5')

def enable_repository(processor, repository):
    """Attach verified content/aliases to an existing processor, not runtime roles."""
    processor.blue.language.enable_repository(repository)
    processor.blue.refresh()

def disable_repository(processor, name):
    """Remove authoring availability; already retained exact history remains valid."""
    processor.blue.language.disable_repository(name)
    processor.blue.refresh()

__all__ = ['Repository', 'RepositoryError', 'bundled', 'repository_20260921', 'prepared_repository_20260921', 'enable_repository', 'disable_repository']
