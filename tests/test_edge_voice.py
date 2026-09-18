import unittest

from edge_voice import EdgeVoiceError, EdgeVoiceService


class EdgeVoiceServiceTest(unittest.TestCase):
    def test_synthesizes_and_caches_audio(self):
        calls = []

        def renderer(text, voice, rate):
            calls.append((text, voice, rate))
            return b"audio-neural"

        service = EdgeVoiceService(renderer=renderer, cache_size=2)
        first = service.synthesize("  Atenção.  TEC1. ")
        second = service.synthesize("Atenção. TEC1.")
        self.assertEqual(first, b"audio-neural")
        self.assertEqual(second, first)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], "pt-BR-FranciscaNeural")

    def test_rejects_invalid_input(self):
        service = EdgeVoiceService(renderer=lambda *_: b"audio")
        with self.assertRaises(ValueError):
            service.synthesize("")
        with self.assertRaises(ValueError):
            service.synthesize("teste", voice="voz-desconhecida")

    def test_rejects_empty_renderer_result(self):
        service = EdgeVoiceService(renderer=lambda *_: b"")
        with self.assertRaises(EdgeVoiceError):
            service.synthesize("teste")


if __name__ == "__main__":
    unittest.main()
