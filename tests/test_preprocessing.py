"""Tests for the text preprocessing pipeline.

Pipeline ini harus identik dengan yang dipakai saat training model.
Test di sini mengunci perilaku itu: kalau salah satu gagal, model menerima
bentuk teks yang tidak pernah dilihatnya saat belajar.
"""

from app.services.preprocessing import (
    light_preprocess,
    normalize_obfuscation,
    preprocess,
)


class TestLightPreprocess:
    """Unit tests for light_preprocess()."""

    def test_case_folding(self):
        assert light_preprocess("HELLO World") == "hello world"

    def test_url_replacement(self):
        result = light_preprocess("Visit https://example.com/page now")
        assert "HTTPURL" in result
        assert "https://" not in result

    def test_www_url_replacement(self):
        result = light_preprocess("See www.example.com for info")
        assert "HTTPURL" in result
        assert "www." not in result

    def test_mention_replacement(self):
        result = light_preprocess("Hey @Budi what's up")
        assert "@USER" in result
        assert "@Budi" not in result

    def test_multiple_mentions(self):
        assert light_preprocess("@Alice and @Bob") == "@USER and @USER"

    def test_placeholder_tokens_survive_deleet(self):
        # HTTPURL / @USER huruf besar justru supaya tidak ikut di-deleet.
        result = light_preprocess("cek https://a.co @budi")
        assert "HTTPURL" in result and "@USER" in result

    def test_whitespace_normalisation(self):
        assert light_preprocess("hello   world\t\nfoo") == "hello world foo"

    def test_leading_trailing_whitespace(self):
        assert light_preprocess("  hello  ") == "hello"

    def test_emoji_demojized_to_indonesian(self):
        # Emoji tidak dibuang tapi diterjemahkan jadi token teks berbahasa Indonesia.
        result = light_preprocess("marah \U0001f621")
        assert ":" in result
        assert "\U0001f621" not in result

    def test_combined(self):
        result = light_preprocess("Halo @Budi lihat https://t.co/abc  !")
        assert result == "halo @USER lihat HTTPURL !"

    def test_empty_string(self):
        assert light_preprocess("") == ""

    def test_only_whitespace(self):
        assert light_preprocess("   ") == ""

    def test_no_transformation_needed(self):
        assert light_preprocess("halo dunia") == "halo dunia"

    def test_non_string_input(self):
        assert light_preprocess(123) == "123"

    def test_preprocess_is_alias(self):
        assert preprocess("HALO") == light_preprocess("HALO")


class TestNormalizeObfuscation:
    """De-leet, un-spacing, dan squeeze huruf berulang."""

    def test_leet_digits_in_word(self):
        assert normalize_obfuscation("b0d0h") == "bodoh"

    def test_leet_symbols_in_word(self):
        assert normalize_obfuscation("b@bi") == "babi"

    def test_leet_only_applies_mid_word(self):
        # Angka di tepi kata tidak diubah; kalau tidak, "g0" jadi "go".
        assert normalize_obfuscation("g0") == "g0"

    def test_standalone_number_untouched(self):
        assert normalize_obfuscation("gue 2024 ke sini") == "gue 2024 ke sini"

    def test_spaced_word(self):
        assert normalize_obfuscation("b o d o h") == "bodoh"

    def test_dotted_word(self):
        assert normalize_obfuscation("b.o.d.o.h") == "bodoh"

    def test_repeated_letters_squeezed_to_two(self):
        assert normalize_obfuscation("bodohhhhh") == "bodohh"

    def test_double_letters_preserved(self):
        # "ss" asli (mis. "massa") tidak boleh dipotong.
        assert normalize_obfuscation("massa") == "massa"

    def test_full_pipeline_on_obfuscated_insult(self):
        assert light_preprocess("DASAR B0D0H!!") == "dasar bodoh!!"
