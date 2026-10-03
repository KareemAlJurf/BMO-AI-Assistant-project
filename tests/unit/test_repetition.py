import json
from unittest.mock import Mock

import pytest
import core.llm as llm

LINE = "I'm your BMO, and I'll always be by your side."


def test_stops_observed_loop():
    text = LINE + " Because you can depend on me. " + LINE + " More looping."
    safe, stopped = llm.truncate_repeated_sentences(text)
    assert stopped
    assert safe == LINE + " Because you can depend on me."


@pytest.mark.parametrize('text', [
    'Yay! Yay! Let us play!',
    'The dinosaurs stomp across the plain.\nTheir shadows dance beneath the rain.\nGood night!',
    LINE + ' A different sentence finishes this complete answer.',
    '<think>' + LINE * 2 + '</think>Hello!',
    '{"action":"set_expression","value":"happy"}\n' * 2,
])
def test_preserves_normal_text_and_actions(text):
    assert llm.truncate_repeated_sentences(text) == (text, False)


@pytest.mark.parametrize('chunks', [
    [LINE, ' ' + LINE, ' Must never be consumed.'],
    list(LINE + ' ' + LINE) + [' Must never be consumed.'],
    [LINE + ' ' + LINE + ' More text in the same chunk.'],
    [LINE, ' ' + LINE[:-1]],
])
def test_stream_never_speaks_or_saves_duplicate(monkeypatch, chunks):
    brain = llm.Brain.__new__(llm.Brain)
    brain.history = [{'role': 'system', 'content': 'Be helpful.'}]
    brain.save_history = Mock()
    brain._trim_history = Mock()
    response = Mock(status_code=200)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.iter_lines.return_value = iter(
        json.dumps({'message': {'content': chunk}}).encode() for chunk in chunks
    )
    post = Mock(return_value=response)
    monkeypatch.setattr(llm.requests, 'post', post)
    spoken = ''.join(brain.stream_think('Who is your best friend?'))
    assert spoken.strip() == LINE
    assert brain.history[-1]['content'].strip() == LINE
    options = post.call_args.kwargs['json']['options']
    assert options['num_predict'] == 384
    assert options['repeat_penalty'] == 1.15
    if chunks[-1].endswith('.'):
        response.close.assert_called_once()


def test_nonstream_filters_before_saving(monkeypatch):
    brain = llm.Brain.__new__(llm.Brain)
    brain.history = [{'role': 'system', 'content': 'Be helpful.'}]
    brain._trim_history = Mock()
    response = Mock(status_code=200)
    response.json.return_value = {'message': {'content': LINE + ' ' + LINE}}
    monkeypatch.setattr(llm.requests, 'post', Mock(return_value=response))
    assert brain.think('Who is your best friend?') == LINE
    assert brain.history[-1]['content'] == LINE
