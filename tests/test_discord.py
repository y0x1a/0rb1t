from orb1t.integrations.discord_rpc import (
    ACTIVITY_PHRASES,
    REPO_URL,
    DiscordConfig,
    DiscordRPC,
    build_activity,
)


def test_build_activity_uses_name_and_button():
    cfg = DiscordConfig(enabled=True, client_id='123', large_image='orb1t', large_text='0rb1t')
    a = build_activity('Nova', cfg, now=0)
    assert a['details'] == ACTIVITY_PHRASES[0].format(name='Nova')
    assert a['state'] == 'github.com/y0x1a/0rb1t'
    assert a['buttons'][0] == {'label': 'GitHub', 'url': 'https://github.com/y0x1a/0rb1t'}
    assert a['assets']['large_image'] == 'orb1t'


def test_details_rotate_once_per_minute_without_ai_filler():
    cfg = DiscordConfig(client_id='123')
    minutes = range(0, len(ACTIVITY_PHRASES) * 60, 60)
    details = [build_activity('0rb1t', cfg, now=m)['details'] for m in minutes]
    assert details == [p.format(name='0rb1t') for p in ACTIVITY_PHRASES]
    assert details == [build_activity('0rb1t', cfg, now=m + 59)['details'] for m in minutes]
    assert details[0] == build_activity('0rb1t', cfg, now=len(ACTIVITY_PHRASES) * 60)['details']
    assert all('ai' not in d.lower().split() for d in details)
    assert all(d.endswith(' 0rb1t') for d in details)


def test_state_matches_repo_url():
    assert REPO_URL == 'github.com/y0x1a/0rb1t'
    assert build_activity('0rb1t', DiscordConfig())['state'] == REPO_URL


def test_discord_noop_without_client_id():
    rpc = DiscordRPC()
    assert rpc.connect('') is False
    assert rpc.send_activity({'details': 'x'}) is False
