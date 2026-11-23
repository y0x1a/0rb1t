from orb1t.integrations.discord_rpc import DiscordConfig, DiscordRPC, build_activity


def test_build_activity_uses_name_and_button():
    cfg = DiscordConfig(enabled=True, client_id='123', large_image='orb1t', large_text='0rb1t')
    a = build_activity('Nova', cfg)
    assert a['details'] == 'Talking to Nova'
    assert a['state'] == 'AI-powered development environment'
    assert a['buttons'][0]['url'] == 'https://github.com/y0x1a/0rb1t'
    assert a['assets']['large_image'] == 'orb1t'


def test_discord_noop_without_client_id():
    rpc = DiscordRPC()
    assert rpc.connect('') is False
    assert rpc.send_activity({'details':'x'}) is False
