from dataclasses import replace
from fjaraskupan import State

def test_parse_announce():
    state = State().replace_from_manufacture_data(b"HOODFJAR\x00\x00\x00\x00\x00\x00\x00")

    assert state == State(
        light_on=False,
        after_cooking_fan_speed=0,
        after_cooking_on=False,
        carbon_filter_available=False,
        fan_speed=0,
        grease_filter_full=False,
        carbon_filter_full=False,
        dim_level=0,
        periodic_venting=0,
        periodic_venting_on=False
    )

    state = State().replace_from_manufacture_data(b"HOODFJAR\x01\x02\x00\x00\x00\x30\x04")
    assert state == State(
        light_on=False,
        after_cooking_fan_speed=2,
        after_cooking_on=False,
        carbon_filter_available=False,
        fan_speed=1,
        grease_filter_full=False,
        carbon_filter_full=False,
        dim_level=0x30,
        periodic_venting=0x04,
        periodic_venting_on=False
    )

    state = State().replace_from_manufacture_data(b"HOODFJAR\x01\x02\x01\x00\x00\x30\x00")
    assert state == replace(state, light_on=True)

    state = State().replace_from_manufacture_data(b"HOODFJAR\x01\x02\x03\x00\x00\x30\x00")
    assert state == replace(state, after_cooking_on=True)

    state = State().replace_from_manufacture_data(b"HOODFJAR\x01\x02\x07\x00\x00\x30\x00")
    assert state == replace(state, periodic_venting_on=True)

    state = State().replace_from_manufacture_data(b"HOODFJAR\x01\x02\x07\x01\x00\x30\x00")
    assert state == replace(state, grease_filter_full=True)

    state = State().replace_from_manufacture_data(b"HOODFJAR\x01\x02\x07\x03\x00\x30\x00")
    assert state == replace(state, carbon_filter_full=True)

    state = State().replace_from_manufacture_data(b"HOODFJAR\x01\x02\x07\x07\x00\x30\x00")
    assert state == replace(state, carbon_filter_available=True)



def test_parse_rx():
    state = State().replace_from_tx_char(b"12340_____00000")

    assert state == State(
        light_on=False,
        after_cooking_fan_speed=0,
        after_cooking_on=False,
        carbon_filter_available=False,
        fan_speed=0,
        grease_filter_full=False,
        carbon_filter_full=False,
        dim_level=0,
        periodic_venting=0,
        periodic_venting_on=False
    )

    state = State().replace_from_tx_char(b"12348_____00000")
    assert state == replace(state, fan_speed=8)

    state = State().replace_from_tx_char(b"12348_____10000")
    assert state == replace(state, dim_level=100)

    state = State().replace_from_tx_char(b"12348_____10100")
    assert state == replace(state, dim_level=0)

    state = State().replace_from_tx_char(b"12348_____10059")
    assert state == replace(state, periodic_venting=59)

    state = State().replace_from_tx_char(b"12348_____10061")
    assert state == replace(state, periodic_venting=0)
