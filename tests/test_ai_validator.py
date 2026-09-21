"""آزمون اعتبارسنج خروجی هوش مصنوعی."""

from __future__ import annotations

from ai.agent.validator import ResponseValidator


def _validator() -> ResponseValidator:
    """اعتبارسنج با محدودیت‌های نمونه."""
    return ResponseValidator(max_leverage=5, min_risk_reward=1.5)


def test_clean_json_is_accepted() -> None:
    """JSON سالم باید پذیرفته شود."""
    outcome = _validator().validate_signal(
        '{"signal":"LONG","entry":{"min":100,"max":101},"stop_loss":97,'
        '"take_profit":[105,110,115],"leverage":3,"confidence":70,"trend":"BULLISH",'
        '"market_structure":"BREAKOUT","reason":"test","invalidation":"close below 97"}'
    )
    assert outcome.valid
    assert outcome.data["signal"] == "LONG"


def test_json_inside_code_fence_is_extracted() -> None:
    """مدل‌ها اغلب JSON را داخل بلوک کد می‌گذارند؛ باید استخراج شود."""
    text = 'Sure!\n```json\n{"signal":"WAIT","confidence":40,"reason":"conflicting timeframes"}\n```\nHope that helps.'
    outcome = _validator().validate_signal(text)
    assert outcome.valid
    assert outcome.data["signal"] == "WAIT"


def test_trailing_comma_is_repaired() -> None:
    """کامای اضافی یک خطای رایج مدل‌های کوچک است و باید ترمیم شود."""
    outcome = _validator().validate_signal('{"signal":"WAIT","confidence":30,"reason":"x",}')
    assert outcome.valid


def test_non_json_is_rejected() -> None:
    """متن آزاد بدون JSON باید رد شود."""
    outcome = _validator().validate_signal("I think Bitcoin looks bullish today.")
    assert not outcome.valid
    assert "not valid JSON" in outcome.error_text


def test_long_with_stop_above_entry_is_rejected() -> None:
    """حد ضرر در سمت اشتباه باید رد شود."""
    outcome = _validator().validate_signal(
        '{"signal":"LONG","entry":100,"stop_loss":105,"take_profit":[95],"confidence":80,"reason":"x"}'
    )
    assert not outcome.valid


def test_unordered_take_profits_are_rejected() -> None:
    """اهداف نامرتب باید رد شوند."""
    outcome = _validator().validate_signal(
        '{"signal":"LONG","entry":100,"stop_loss":95,"take_profit":[120,105,130],'
        '"confidence":60,"reason":"x","invalidation":"y"}'
    )
    assert not outcome.valid
    assert "ascending" in outcome.error_text


def test_excessive_leverage_is_clamped() -> None:
    """اهرم بیش از حد باید به سقف کاربر محدود شود، نه اینکه سیگنال رد شود."""
    outcome = _validator().validate_signal(
        '{"signal":"SHORT","entry":100,"stop_loss":103,"take_profit":[95,90,85],'
        '"leverage":50,"confidence":60,"trend":"BEARISH","market_structure":"BREAKDOWN",'
        '"reason":"x","invalidation":"y"}'
    )
    assert outcome.valid
    assert outcome.data["leverage"] == 5
    assert any("exceeds" in w for w in outcome.warnings)


def test_risk_reward_is_recomputed_from_numbers() -> None:
    """نسبت ریسک به سود باید از روی اعداد واقعی محاسبه و اصلاح شود."""
    outcome = _validator().validate_signal(
        '{"signal":"LONG","entry":100,"stop_loss":90,"take_profit":[130],'
        '"confidence":50,"reason":"x","risk_reward":9.9,"invalidation":"y"}'
    )
    assert outcome.data["risk_reward"] == 3.0


def test_insufficient_data_becomes_wait() -> None:
    """اعلام نبود داده از سوی مدل باید به WAIT تبدیل شود."""
    outcome = _validator().validate_signal('{"signal":"INSUFFICIENT_DATA","confidence":0,"reason":"no candles"}')
    assert outcome.valid
    assert outcome.data["signal"] == "WAIT"


def test_confidence_out_of_range_is_rejected() -> None:
    """اطمینان خارج از بازه صفر تا صد باید رد شود."""
    outcome = _validator().validate_signal('{"signal":"WAIT","confidence":180,"reason":"x"}')
    assert not outcome.valid


def test_wait_signal_clears_price_fields() -> None:
    """سیگنال انتظار نباید قیمت ورود یا حد ضرر داشته باشد."""
    outcome = _validator().validate_signal(
        '{"signal":"WAIT","entry":100,"stop_loss":90,"take_profit":[110],"confidence":30,"reason":"x"}'
    )
    assert outcome.valid
    assert outcome.data["stop_loss"] is None
    assert outcome.data["take_profit"] == []


def test_low_risk_reward_raises_warning() -> None:
    """نسبت ریسک به سود پایین باید هشدار بدهد."""
    outcome = _validator().validate_signal(
        '{"signal":"SHORT","entry":100,"stop_loss":103,"take_profit":[97.4],'
        '"leverage":2,"confidence":60,"trend":"BEARISH","market_structure":"BREAKDOWN",'
        '"reason":"x","invalidation":"y"}'
    )
    assert outcome.valid
    assert any("below the user minimum" in w for w in outcome.warnings)
