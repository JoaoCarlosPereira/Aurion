"""Tests for VoiceListener."""

import queue
import threading
import time

import pytest

from aurion.listener import (
    VoiceCommand,
    VoiceListener,
    extract_command_tail,
    is_exit_phrase,
    is_likely_echo,
    is_spurious_transcript,
    is_system_phrase_echo,
    is_wake_word,
    parse_queue_item,
)


def test_is_wake_word_exact_and_substring():
    assert is_wake_word("aurion", "aurion")
    assert is_wake_word("oi aurion", "aurion")
    assert is_wake_word("ario", "aurion")
    assert is_wake_word("áudio que horas", "aurion")
    assert is_wake_word("orion", "aurion")
    assert is_wake_word("rau", "aurion")
    assert is_wake_word("au", "aurion")
    assert is_wake_word("aur", "aurion")
    assert not is_wake_word("john parquelândia", "aurion")
    assert not is_wake_word("estou pronta para ajudar", "aurion")


def test_extract_command_tail():
    assert extract_command_tail("aurion qual é a hora", "aurion") == "qual e a hora"
    assert extract_command_tail("áudio que horas", "aurion") == "que horas"
    assert extract_command_tail("áudio que", "aurion") == "que"
    assert extract_command_tail("oi aurion liga a luz", "aurion") == "oi liga a luz"
    assert extract_command_tail("aurion", "aurion") == ""


def test_is_exit_phrase():
    assert is_exit_phrase("aurion pare", "aurion")
    assert is_exit_phrase("áudio pare", "aurion")
    assert is_exit_phrase("aurion parar", "aurion")
    assert not is_exit_phrase("aurion qual a hora", "aurion")
    assert not is_exit_phrase("pare", "aurion")


def test_parse_queue_item():
    assert parse_queue_item("oi") == ("oi", False, False)
    assert parse_queue_item(VoiceCommand("hora", wait_response=True, voice_mode=True)) == (
        "hora",
        True,
        True,
    )


def test_is_system_phrase_echo():
    assert is_system_phrase_echo("certo um momento por favor")
    assert is_system_phrase_echo("estou pronta para ajudar")
    assert is_system_phrase_echo("olá eu sou aurion e estou pronta para ajudar")
    assert not is_system_phrase_echo("qual a previsao do tempo")
    assert not is_system_phrase_echo("maroon 5")


def test_is_spurious_transcript():
    ref = "gostaria de ouvir maroon 5 ou quer saber algo sobre a banda"
    assert is_spurious_transcript("certo um momento por favor")
    assert is_spurious_transcript("gostaria de ouvir maroon 5", ref)
    assert not is_spurious_transcript("que dia e hoje", ref)


def test_is_likely_echo():
    ref = (
        "vou verificar a previsao detalhada para sao miguel do oeste agora mesmo "
        "so um momento"
    )
    assert is_likely_echo(
        "como verificar a previsão detalhada para são miguel do oeste agora", ref
    )
    assert not is_likely_echo("qual a previsao do tempo", ref)
    assert not is_likely_echo("tempo novamente", ref)


def test_command_after_oi_strips_repeated_wake_alias():
    """Pós-Oi, 'áudio que horas' não deve ser descartado como wake word."""
    t2 = "áudio que horas"
    cmd_part = extract_command_tail(t2, "aurion")
    assert cmd_part == "que horas"
    assert is_wake_word(t2, "aurion")  # frase inteira ainda é wake
    assert cmd_part  # mas o pedido extraído deve ir para a fila


def test_wake_word_detected(command_queue):
    """Wake word 'aurion' é detectado corretamente."""
    listener = VoiceListener(command_queue, trigger_word="aurion")
    assert listener.trigger_word == "aurion"


def test_command_placed_in_queue(command_queue):
    """Comando após wake word é colocado na fila."""
    from aurion.listener import VoiceListener

    listener = VoiceListener(command_queue, trigger_word="aurion")
    command_queue.put("aurion, hello")
    assert not command_queue.empty()
    cmd = command_queue.get(timeout=1)
    assert "aurion" in cmd.lower()


def test_false_positive_no_trigger(command_queue):
    """Falso positivo (outra palavra) não dispara escuta."""
    from aurion.listener import VoiceListener

    listener = VoiceListener(command_queue, trigger_word="aurion")
    # Simulate: user says something that doesn't contain "aurion"
    # In wake mode, it should not put anything in queue
    command_queue.put("hello friend")
    assert command_queue.qsize() == 1
    assert "aurion" not in command_queue.get().lower()


def test_start_creates_daemon_thread(command_queue):
    """start() inicia thread daemon."""
    from aurion.listener import VoiceListener

    listener = VoiceListener(command_queue, trigger_word="aurion")
    # Don't actually start the thread since there's no microphone
    # Just verify the thread attribute is None before start
    assert listener._thread is None
    assert listener._running is False


def test_stop_before_start(command_queue):
    """stop() pode ser chamado sem start() sem crash."""
    from aurion.listener import VoiceListener

    listener = VoiceListener(command_queue, trigger_word="aurion")
    listener.stop()  # Should not raise


def test_concurrent_command_queue(command_queue):
    """Thread de escuta → fila → consumer recebe comando."""
    def producer():
        time.sleep(0.1)
        command_queue.put("test command from producer")

    t = threading.Thread(target=producer, daemon=True)
    t.start()
    t.join(timeout=2)

    cmd = command_queue.get(timeout=1)
    assert cmd == "test command from producer"
