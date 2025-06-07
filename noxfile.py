import nox

@nox.session(name="setup")
def setup(session):
    session.install("typer==0.12.3", "rich==13.7.1")
