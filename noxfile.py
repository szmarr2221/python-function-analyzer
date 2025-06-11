import nox

@nox.session(name="setup")
def setup(session):
    session.install(
        "typer==0.12.3",
        "rich==13.7.1",
        "pygls==1.1.1",
        "lsprotocol==2023.0.0b1",  # Match pygls requirement
        "pydantic==1.7.1"
    )
