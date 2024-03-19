from unittest.mock import mock_open, patch

import pytest
from pydantic import SecretStr, ValidationError

from kolkra_ng.config import Config, read_config


def test_good_config():
    content = b"""\
bot_token = "MTA4NDI0NzI3NDE2MDM5NDI4MA.GLqzML.YHdeWqA3x5s297MIfJ44YwDkrBfT04EEaABm7g"
guild_id = 740944141122535465
"""
    with patch("builtins.open", mock_open(read_data=content)):
        assert read_config() == Config(
            bot_token=SecretStr("MTA4NDI0NzI3NDE2MDM5NDI4MA.GLqzML.YHdeWqA3x5s297MIfJ44YwDkrBfT04EEaABm7g"),
            guild_id=740944141122535465,
        )


def test_bad_token():
    content = b"""\
bot_token = "blahblah.thisisdef.notatoken"
guild_id = 740944141122535465
"""
    with pytest.raises(ValidationError), patch("builtins.open", mock_open(read_data=content)):
        read_config()
