from infrastructure.signal_io.playback import IQPlayback


def test_replay_pipeline_basic(sample_iq_session):
    playback = IQPlayback(
        session_dir=sample_iq_session,
        realtime=False,
        speed=10.0,
    )

    playback.start()
    frames = list(playback)
    playback.stop()

    assert len(frames) == 1
