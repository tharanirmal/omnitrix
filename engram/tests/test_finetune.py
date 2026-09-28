import json
from collections import Counter

from engram.finetune import chat, split_of, write_dataset
from engram.judge import choice, noul
from engram.labels import Example


def test_split_is_stable_per_conversation_and_roughly_proportional():
    assert split_of("thread:model review") == split_of("thread:model review")
    shares = Counter(split_of(f"thread:{i}") for i in range(10_000))
    assert abs(shares["train"] / 10_000 - 0.7) < 0.03 and abs(shares["test"] / 10_000 - 0.2) < 0.03


def test_chat_row_answers_with_the_label_key():
    folder = choice("filed", "Which folder?", ["hr", "research"])
    row = chat(Example(folder, "An offer letter", "item:1", "research", "behaviour", "thread:offer"))
    assert [m["role"] for m in row["messages"]] == ["system", "user", "assistant"]
    assert row["messages"][-1]["content"] == "B" and "B) research" in row["messages"][1]["content"]
    no = Example(noul("x", "Is it?"), "m", "item:2", "no", "benchmark", "item:2")
    assert chat(no)["messages"][-1]["content"] == "no"


def test_write_dataset_keeps_each_conversation_in_one_split(tmp_path):
    q = noul("replied", "Reply?")
    examples = [Example(q, f"msg {i}", f"item:{i}", "yes" if i % 2 else "no", "behaviour", f"thread:{i // 4}")
                for i in range(200)]                                    # 50 threads of 4 messages
    counts = write_dataset(examples, tmp_path)
    lines = {s: (tmp_path / f"{s}.jsonl").read_text().splitlines() for s in ("train", "valid", "test")}
    assert sum(len(v) for v in lines.values()) == 200 == sum(sum(c.values()) for c in counts.values())
    seen = {s: {json.loads(line)["messages"][1]["content"] for line in lines[s]} for s in lines}
    thread_split = {}
    for e in examples:
        split = next(s for s in seen if e.question.render(e.state) in seen[s])
        assert thread_split.setdefault(e.group, split) == split           # never two splits for one thread


class Template:
    """A chat template in miniature; `think_in_training` says whether rendered training rows carry the empty
    thinking block that inference with thinking disabled puts before the answer (Qwen3 does)."""

    def __init__(self, think_in_training: bool):
        self.think_in_training = think_in_training

    def apply_chat_template(self, messages, add_generation_prompt=False, enable_thinking=True):
        text = "".join(f"<{m['role']}>{m['content']}" for m in messages if m["role"] != "assistant")
        if add_generation_prompt:
            text += "<assistant>" + ("" if enable_thinking else "<think></think>")
        for m in messages:
            if m["role"] == "assistant":
                text += "<assistant>" + ("<think></think>" if self.think_in_training else "") + m["content"]
        return list(text.encode())


def test_template_check_catches_a_train_inference_mismatch():
    import pytest

    from engram.finetune import check_template

    check_template(Template(think_in_training=True))
    with pytest.raises(RuntimeError):
        check_template(Template(think_in_training=False))


def test_rows_too_long_to_train_on_are_left_out_so_the_answer_is_never_cut(tmp_path):
    """mlx-lm cuts an over-long row from the end, which removes the masked answer: 0/0 loss, NaN weights."""
    import json

    from engram.finetune import fit

    class Words:                                        # one token per word
        def apply_chat_template(self, messages):
            return " ".join(m["content"] for m in messages).split()

    def row(n):
        return json.dumps({"messages": [{"role": "user", "content": "w " * n},
                                        {"role": "assistant", "content": "yes"}]})

    data = tmp_path / "v2"
    data.mkdir()
    (data / "train.jsonl").write_text(row(5) + "\n" + row(50) + "\n")
    (data / "valid.jsonl").write_text(row(5) + "\n")
    (data / "test.jsonl").write_text(row(50) + "\n")
    out = fit(data, Words(), max_tokens=20)
    assert out == tmp_path / "v2-fit"
    assert (out / "train.jsonl").read_text().count("\n") == 1 and (out / "test.jsonl").read_text() == row(50) + "\n"
    assert fit(out, Words(), max_tokens=20) == out                  # nothing too long: the same directory
