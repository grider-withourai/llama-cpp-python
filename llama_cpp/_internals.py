from __future__ import annotations

import os

from typing import (
    List,
    Optional,
    Sequence,
)

import ctypes

import numpy as np
import numpy.typing as npt

from .llama_types import *
from .llama_grammar import LlamaGrammar

import llama_cpp.llama_cpp as llama_cpp

from ._utils import suppress_stdout_stderr



class _LlamaModel:
    """Intermediate Python wrapper for a llama.cpp llama_model.

    NOTE: For stability it's recommended you use the Llama class instead."""

    _llama_free_model = None

    def __init__(
        self,
        *,
        path_model: str,
        params: llama_cpp.llama_model_params,
        verbose: bool = True,
    ):
        self.path_model = path_model
        self.params = params
        self.verbose = verbose

        self._llama_free_model = llama_cpp._lib.llama_free_model  # type: ignore

        if not os.path.exists(path_model):
            raise ValueError(f"Model path does not exist: {path_model}")

        with suppress_stdout_stderr(disable=self.verbose):
            self.model = llama_cpp.llama_load_model_from_file(
                self.path_model.encode("utf-8"), self.params
            )

    def __del__(self):
        with suppress_stdout_stderr(disable=self.verbose):
            if self.model is not None and self._llama_free_model is not None:
                self._llama_free_model(self.model)
                self.model = None

    def vocab_type(self) -> int:
        assert self.model is not None
        return llama_cpp.llama_vocab_type(self.model)

    def n_vocab(self) -> int:
        assert self.model is not None
        return llama_cpp.llama_n_vocab(self.model)

    def n_ctx_train(self) -> int:
        assert self.model is not None
        return llama_cpp.llama_n_ctx_train(self.model)

    def n_embd(self) -> int:
        assert self.model is not None
        return llama_cpp.llama_n_embd(self.model)

    def rope_freq_scale_train(self) -> float:
        assert self.model is not None
        return llama_cpp.llama_rope_freq_scale_train(self.model)

    def desc(self) -> str:
        assert self.model is not None
        buf = ctypes.create_string_buffer(1024)
        llama_cpp.llama_model_desc(self.model, buf, 1024)  # type: ignore
        return buf.value.decode("utf-8")

    def size(self) -> int:
        assert self.model is not None
        return llama_cpp.llama_model_size(self.model)

    def n_params(self) -> int:
        assert self.model is not None
        return llama_cpp.llama_model_n_params(self.model)

    def get_tensor(self, name: str) -> ctypes.c_void_p:
        assert self.model is not None
        return llama_cpp.llama_get_model_tensor(self.model, name.encode("utf-8"))

    def apply_lora_from_file(
        self,
        lora_path: str,
        scale: float,
        path_base_model: Optional[str],
        n_threads: int,
    ):
        assert self.model is not None
        return llama_cpp.llama_model_apply_lora_from_file(
            self.model,
            lora_path.encode("utf-8"),
            scale,
            path_base_model.encode("utf-8")
            if path_base_model is not None
            else llama_cpp.c_char_p(0),
            n_threads,
        )

    # Vocab

    def token_get_text(self, token: int) -> str:
        # TODO: Fix
        assert self.model is not None
        return llama_cpp.llama_token_get_text(self.model, token).decode("utf-8")

    def token_get_score(self, token: int) -> float:
        assert self.model is not None
        return llama_cpp.llama_token_get_score(self.model, token)

    def token_get_type(self, token: int) -> int:
        assert self.model is not None
        return llama_cpp.llama_token_get_type(self.model, token)

    # Special tokens

    def token_bos(self) -> int:
        assert self.model is not None
        return llama_cpp.llama_token_bos(self.model)

    def token_eos(self) -> int:
        assert self.model is not None
        return llama_cpp.llama_token_eos(self.model)

    def token_nl(self) -> int:
        assert self.model is not None
        return llama_cpp.llama_token_nl(self.model)

    def token_prefix(self) -> int:
        assert self.model is not None
        return llama_cpp.llama_token_prefix(self.model)

    def token_middle(self) -> int:
        assert self.model is not None
        return llama_cpp.llama_token_middle(self.model)

    def token_suffix(self) -> int:
        assert self.model is not None
        return llama_cpp.llama_token_suffix(self.model)

    def token_eot(self) -> int:
        assert self.model is not None
        return llama_cpp.llama_token_eot(self.model)

    # Tokenization

    def tokenize(self, text: bytes, add_bos: bool, special: bool):
        assert self.model is not None
        n_ctx = self.n_ctx_train()
        tokens = (llama_cpp.llama_token * n_ctx)()
        n_tokens = llama_cpp.llama_tokenize(
            self.model, text, len(text), tokens, n_ctx, add_bos, special
        )
        if n_tokens < 0:
            n_tokens = abs(n_tokens)
            tokens = (llama_cpp.llama_token * n_tokens)()
            n_tokens = llama_cpp.llama_tokenize(
                self.model, text, len(text), tokens, n_tokens, add_bos, special
            )
            if n_tokens < 0:
                raise RuntimeError(
                    f'Failed to tokenize: text="{text}" n_tokens={n_tokens}'
                )
        return list(tokens[:n_tokens])

    def token_to_piece(self, token: int) -> bytes:
        assert self.model is not None
        buf = ctypes.create_string_buffer(32)
        llama_cpp.llama_token_to_piece(self.model, token, buf, 32)  # type: ignore
        return bytes(buf)

    def detokenize(self, tokens: List[int]) -> bytes:
        assert self.model is not None
        output = b""
        size = 32
        buffer = (ctypes.c_char * size)()
        for token in tokens:
            n = llama_cpp.llama_token_to_piece(
                self.model, llama_cpp.llama_token(token), buffer, size
            )
            assert n <= size
            output += bytes(buffer[:n])
        # NOTE: Llama1 models automatically added a space at the start of the prompt
        # this line removes a leading space if the first token is a beginning of sentence token
        return (
            output[1:] if len(tokens) > 0 and tokens[0] == self.token_bos() else output
        )

    @staticmethod
    def default_params():
        """Get the default llama_model_params."""
        return llama_cpp.llama_model_default_params()


class _LlamaContext:
    """Intermediate Python wrapper for a llama.cpp llama_context.

    NOTE: For stability it's recommended you use the Llama class instead."""

    _llama_free = None

    def __init__(
        self,
        *,
        model: _LlamaModel,
        params: llama_cpp.llama_context_params,
        verbose: bool = True,
    ):
        self.model = model
        self.params = params
        self.verbose = verbose

        self._llama_free = llama_cpp._lib.llama_free  # type: ignore

        with suppress_stdout_stderr(disable=self.verbose):
            self.ctx = llama_cpp.llama_new_context_with_model(
                self.model.model, self.params
            )

    def __del__(self):
        with suppress_stdout_stderr(disable=self.verbose):
            if self.ctx is not None and self._llama_free is not None:
                self._llama_free(self.ctx)
                self.ctx = None

    def n_ctx(self) -> int:
        assert self.ctx is not None
        return llama_cpp.llama_n_ctx(self.ctx)

    def kv_cache_clear(self):
        assert self.ctx is not None
        llama_cpp.llama_kv_cache_clear(self.ctx)

    def kv_cache_seq_rm(self, seq_id: int, p0: int, p1: int):
        assert self.ctx is not None
        llama_cpp.llama_kv_cache_seq_rm(self.ctx, seq_id, p0, p1)

    def kv_cache_seq_cp(self, seq_id_src: int, seq_id_dst: int, p0: int, p1: int):
        assert self.ctx is not None
        llama_cpp.llama_kv_cache_seq_cp(self.ctx, seq_id_src, seq_id_dst, p0, p1)

    def kv_cache_seq_keep(self, seq_id: int):
        assert self.ctx is not None
        llama_cpp.llama_kv_cache_seq_keep(self.ctx, seq_id)

    def kv_cache_seq_shift(self, seq_id: int, p0: int, p1: int, shift: int):
        assert self.ctx is not None
        llama_cpp.llama_kv_cache_seq_shift(self.ctx, seq_id, p0, p1, shift)

    def get_state_size(self) -> int:
        assert self.ctx is not None
        return llama_cpp.llama_get_state_size(self.ctx)

    # TODO: copy_state_data

    # TODO: set_state_data

    # TODO: llama_load_session_file

    # TODO: llama_save_session_file

    def decode(self, batch: "_LlamaBatch"):
        assert self.ctx is not None
        assert batch.batch is not None
        return_code = llama_cpp.llama_decode(
            ctx=self.ctx,
            batch=batch.batch,
        )
        if return_code != 0:
            raise RuntimeError(f"llama_decode returned {return_code}")

    def set_n_threads(self, n_threads: int, n_threads_batch: int):
        assert self.ctx is not None
        llama_cpp.llama_set_n_threads(self.ctx, n_threads, n_threads_batch)

    def get_logits(self):
        assert self.ctx is not None
        return llama_cpp.llama_get_logits(self.ctx)

    def get_logits_ith(self, i: int):
        assert self.ctx is not None
        return llama_cpp.llama_get_logits_ith(self.ctx, i)

    def get_embeddings(self):
        assert self.ctx is not None
        return llama_cpp.llama_get_embeddings(self.ctx)

    # Sampling functions

    def set_rng_seed(self, seed: int):
        assert self.ctx is not None
        llama_cpp.llama_set_rng_seed(self.ctx, seed)

    def sample_repetition_penalties(
        self,
        candidates: "_LlamaTokenDataArray",
        last_tokens_data: "llama_cpp.Array[llama_cpp.llama_token]",
        penalty_last_n: int,
        penalty_repeat: float,
        penalty_freq: float,
        penalty_present: float,
    ):
        assert self.ctx is not None
        llama_cpp.llama_sample_repetition_penalties(
            self.ctx,
            ctypes.byref(candidates.candidates),  # type: ignore
            last_tokens_data,
            penalty_last_n,
            penalty_repeat,
            penalty_freq,
            penalty_present,
        )

    def sample_classifier_free_guidance(
        self,
        candidates: "_LlamaTokenDataArray",
        guidance_ctx: "_LlamaContext",
        scale: float,
    ):
        assert self.ctx is not None
        assert guidance_ctx.ctx is not None
        llama_cpp.llama_sample_classifier_free_guidance(
            self.ctx,
            ctypes.byref(candidates.candidates),  # type: ignore
            guidance_ctx.ctx,
            scale,
        )

    def sample_softmax(self, candidates: "_LlamaTokenDataArray"):
        assert self.ctx is not None
        llama_cpp.llama_sample_softmax(
            self.ctx,
            ctypes.byref(candidates.candidates),  # type: ignore
        )

    def sample_top_k(self, candidates: "_LlamaTokenDataArray", k: int, min_keep: int):
        assert self.ctx is not None
        llama_cpp.llama_sample_top_k(
            self.ctx, ctypes.byref(candidates.candidates), k, min_keep  # type: ignore
        )

    def sample_top_p(self, candidates: "_LlamaTokenDataArray", p: float, min_keep: int):
        assert self.ctx is not None
        llama_cpp.llama_sample_top_p(
            self.ctx, ctypes.byref(candidates.candidates), p, min_keep  # type: ignore
        )

    def sample_min_p(self, candidates: "_LlamaTokenDataArray", p: float, min_keep: int):
        assert self.ctx is not None
        llama_cpp.llama_sample_min_p(
            self.ctx, ctypes.byref(candidates.candidates), p, min_keep  # type: ignore
        )

    def sample_tail_free(
        self, candidates: "_LlamaTokenDataArray", z: float, min_keep: int
    ):
        assert self.ctx is not None
        llama_cpp.llama_sample_tail_free(
            self.ctx, ctypes.byref(candidates.candidates), z, min_keep  # type: ignore
        )

    def sample_typical(
        self, candidates: "_LlamaTokenDataArray", p: float, min_keep: int
    ):
        assert self.ctx is not None
        llama_cpp.llama_sample_typical(
            self.ctx, ctypes.byref(candidates.candidates), p, min_keep  # type: ignore
        )

    def sample_temp(self, candidates: "_LlamaTokenDataArray", temp: float):
        assert self.ctx is not None
        llama_cpp.llama_sample_temp(
            self.ctx, ctypes.byref(candidates.candidates), temp  # type: ignore
        )

    def sample_grammar(self, candidates: "_LlamaTokenDataArray", grammar: LlamaGrammar):
        assert self.ctx is not None
        assert grammar.grammar is not None
        llama_cpp.llama_sample_grammar(
            self.ctx,
            ctypes.byref(candidates.candidates),  # type: ignore
            grammar.grammar,
        )

    def sample_token_mirostat(
        self,
        candidates: "_LlamaTokenDataArray",
        tau: float,
        eta: float,
        m: int,
        mu: float,
    ) -> int:
        assert self.ctx is not None
        return llama_cpp.llama_sample_token_mirostat(
            self.ctx,
            ctypes.byref(candidates.candidates),  # type: ignore
            tau,
            eta,
            m,
            ctypes.pointer(ctypes.c_float(mu)),
        )

    def sample_token_mirostat_v2(
        self, candidates: "_LlamaTokenDataArray", tau: float, eta: float, mu: float
    ) -> int:
        assert self.ctx is not None
        return llama_cpp.llama_sample_token_mirostat_v2(
            self.ctx,
            ctypes.byref(candidates.candidates),  # type: ignore
            tau,
            eta,
            ctypes.pointer(ctypes.c_float(mu)),
        )

    def sample_token_greedy(self, candidates: "_LlamaTokenDataArray") -> int:
        assert self.ctx is not None
        return llama_cpp.llama_sample_token_greedy(
            self.ctx,
            ctypes.byref(candidates.candidates),  # type: ignore
        )

    def sample_token(self, candidates: "_LlamaTokenDataArray") -> int:
        assert self.ctx is not None
        return llama_cpp.llama_sample_token(
            self.ctx,
            ctypes.byref(candidates.candidates),  # type: ignore
        )

    # Grammar
    def grammar_accept_token(self, grammar: LlamaGrammar, token: int):
        assert self.ctx is not None
        assert grammar.grammar is not None
        llama_cpp.llama_grammar_accept_token(self.ctx, grammar.grammar, token)

    def reset_timings(self):
        assert self.ctx is not None
        llama_cpp.llama_reset_timings(self.ctx)

    def print_timings(self):
        assert self.ctx is not None
        llama_cpp.llama_print_timings(self.ctx)

    # Utility functions
    @staticmethod
    def default_params():
        """Get the default llama_context_params."""
        return llama_cpp.llama_context_default_params()


class _LlamaBatch:
    _llama_batch_free = None

    def __init__(
        self, *, n_tokens: int, embd: int, n_seq_max: int, verbose: bool = True
    ):
        self.n_tokens = n_tokens
        self.embd = embd
        self.n_seq_max = n_seq_max
        self.verbose = verbose

        self._llama_batch_free = llama_cpp._lib.llama_batch_free  # type: ignore

        with suppress_stdout_stderr(disable=self.verbose):
            self.batch = llama_cpp.llama_batch_init(
                self.n_tokens, self.embd, self.n_seq_max
            )

    def __del__(self):
        with suppress_stdout_stderr(disable=self.verbose):
            if self.batch is not None and self._llama_batch_free is not None:
                self._llama_batch_free(self.batch)
                self.batch = None

    def set_batch(self, batch: Sequence[int], n_past: int, logits_all: bool):
        assert self.batch is not None
        n_tokens = len(batch)
        self.batch.n_tokens = n_tokens
        for i in range(n_tokens):
            self.batch.token[i] = batch[i]
            self.batch.pos[i] = n_past + i
            self.batch.seq_id[i][0] = 0
            self.batch.n_seq_id[i] = 1
            self.batch.logits[i] = logits_all
        self.batch.logits[n_tokens - 1] = True


class _LlamaTokenDataArray:
    def __init__(self, *, n_vocab: int):
        self.n_vocab = n_vocab
        self.candidates_data = np.array(
            [],
            dtype=np.dtype(
                [("id", np.intc), ("logit", np.single), ("p", np.single)], align=True
            ),
        )
        self.candidates_data.resize(3, self.n_vocab, refcheck=False)
        self.candidates = llama_cpp.llama_token_data_array(
            data=self.candidates_data.ctypes.data_as(llama_cpp.llama_token_data_p),
            size=self.n_vocab,
            sorted=False,
        )
        self.default_candidates_data_id = np.arange(self.n_vocab, dtype=np.intc)
        self.default_candidates_data_p = np.zeros(self.n_vocab, dtype=np.single)

    def copy_logits(self, logits: npt.NDArray[np.single]):
        self.candidates_data["id"][:] = self.default_candidates_data_id
        self.candidates_data["logit"][:] = logits
        self.candidates_data["p"][:] = self.default_candidates_data_p
        self.candidates.data = self.candidates_data.ctypes.data_as(
            llama_cpp.llama_token_data_p
        )
        self.candidates.sorted = llama_cpp.c_bool(False)
        self.candidates.size = llama_cpp.c_size_t(self.n_vocab)