from datetime import UTC, datetime

from engram.text import chunk, content_hash, header, split_quoted, thread_key


def test_outlook_reply_is_split():
    body = ("Thanks, Kevin.\n\n -----Original Message-----\n"
            "From: \tKaminski, Vince J\nSent:\tWednesday\nSubject: x\n\nOld")
    new, quoted = split_quoted(body)
    assert new == "Thanks, Kevin."
    assert quoted.startswith("-----Original Message-----")


def test_lotus_forward_banner_spanning_two_lines():
    body = ("FYI\n\nVince\n\n---------------------- Forwarded by Vince J Kaminski/HOU/ECT on 01/10/2000 \n"
            "02:54 PM ---------------------------\n\n\"Edna\" <esai@x.com> on 01/10/2000 11:23:42 AM\nTo: y\n\nReport")
    new, quoted = split_quoted(body)
    assert new == "FYI\n\nVince"
    assert "Forwarded by" in quoted and quoted.endswith("Report")


def test_lotus_reply_headers():
    reply = '"Edna OConnell" <esai@ma.ultranet.com> on 01/10/2000 11:23:42 AM\nPlease respond to esai\nTo: Vince\n\nHi'
    assert split_quoted(f"Sure.\n\n{reply}") == ("Sure.", reply)
    block = "Shirley Crenshaw\n10/03/2000 04:20 PM\nTo: Vince J Kaminski/HOU/ECT@ECT\ncc:\nSubject: Re: lunch\n\nOk"
    assert split_quoted(f"Yes, noon works.\n\n{block}")[0] == "Yes, noon works."


def test_quoted_lines_and_no_false_positives():
    assert split_quoted("Agreed.\n> earlier text\n> more") == ("Agreed.", "> earlier text\n> more")
    prose = "Let's meet on 10/03/2000 11:00 AM\nin my office to discuss the model."
    assert split_quoted(prose) == (prose, "")
    digest = "Tech news\n>From the interesting reading department: chips got faster.\nMore news follows."
    assert split_quoted(digest) == (digest, "")                  # an mbox-escaped '>From' is not a quote
    html = "Hello\n></font></p> residue from an HTML conversion\nreal text"
    assert split_quoted(html) == (html, "")


def test_thread_key_strips_reply_and_forward_prefixes():
    assert thread_key("RE: FW: Re[2]: Budget   Review") == "budget review"
    assert thread_key("Fwd:Re: Hello") == "hello"


def test_chunk_packs_paragraphs_and_respects_max_length():
    text = "\n\n".join(["short paragraph"] * 5 + ["long sentence. " * 200])
    pieces = chunk(text, max_chars=300)
    assert all(len(p) <= 300 for p in pieces)
    assert pieces[0].count("short paragraph") == 5
    assert "".join(pieces).replace(" ", "").replace("\n", "").count("longsentence.") == 200
    assert chunk("") == []


def test_content_hash_ignores_whitespace_differences():
    assert content_hash("a", "b  c\n") == content_hash("a", "b c")
    assert content_hash("a", "b") != content_hash("a", "c")


def test_header_truncates_long_recipient_lists():
    h = header(datetime(2000, 10, 2, tzinfo=UTC), "x@enron.com", ["a", "b", "c", "d", "e"], "Hi")
    assert h == "2000-10-02 | From: x@enron.com | To: a, b, c +2 | Subject: Hi"
