"""Tests for color variation quality — Sprint 16."""
import io
import numpy as np
from PIL import Image


def _make_rgba_image(width, height, r, g, b, transparent_pct=0.5):
    """Cria imagem RGBA com cor sólida e fundo transparente."""
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    # Parte superior: transparente
    split = int(height * transparent_pct)
    # Parte inferior: roupa com cor sólida
    arr[split:, :, 0] = r
    arr[split:, :, 1] = g
    arr[split:, :, 2] = b
    arr[split:, :, 3] = 255
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def _make_rgb_image(width, height, r, g, b):
    """Cria imagem RGB (sem alpha) simulando output do Gemini."""
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    # Metade inferior com cor
    split = height // 2
    arr[split:, :, 0] = r
    arr[split:, :, 1] = g
    arr[split:, :, 2] = b
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def test_restore_alpha_preserva_transparencia():
    """Output deve ter mesmo canal alpha que a original."""
    from app.services.color_variation import _restore_alpha

    original = _make_rgba_image(100, 200, 150, 100, 80, transparent_pct=0.5)
    gemini_output = _make_rgb_image(80, 160, 120, 110, 100)  # Resolução diferente, sem alpha

    result_bytes = _restore_alpha(original, gemini_output)
    result = Image.open(io.BytesIO(result_bytes))

    assert result.mode == "RGBA"
    arr = np.array(result)
    # Top half should be transparent (alpha=0)
    assert arr[:100, :, 3].max() == 0
    # Bottom half should be opaque (alpha=255)
    assert arr[100:, :, 3].min() == 255


def test_restore_alpha_mantem_resolucao_original():
    """Output deve ter mesmas dimensões que a original."""
    from app.services.color_variation import _restore_alpha

    original = _make_rgba_image(400, 600, 150, 100, 80)
    gemini_output = _make_rgb_image(200, 300, 120, 110, 100)  # Metade do tamanho

    result_bytes = _restore_alpha(original, gemini_output)
    result = Image.open(io.BytesIO(result_bytes))

    assert result.size == (400, 600)


def test_quality_metrics_detecta_imagem_ruim():
    """edge_correlation < 0.40 deve ativar quality_warning."""
    from app.services.color_variation import _compute_quality_metrics

    # Original com padrão de textura
    orig_arr = np.zeros((100, 100, 4), dtype=np.uint8)
    orig_arr[50:, :, :3] = 150  # Garment
    orig_arr[50:, :, 3] = 255
    # Adicionar textura vertical
    for i in range(50, 100):
        for j in range(0, 100, 10):
            orig_arr[i, j:j+5, 0] = 200

    orig_buf = io.BytesIO()
    Image.fromarray(orig_arr).save(orig_buf, format="PNG")
    original = orig_buf.getvalue()

    # Resultado completamente diferente (textura horizontal)
    res_arr = np.zeros((100, 100, 4), dtype=np.uint8)
    res_arr[50:, :, :3] = 80  # Muito escuro
    res_arr[50:, :, 3] = 255
    for i in range(50, 100, 10):
        res_arr[i:i+5, :, 1] = 200

    res_buf = io.BytesIO()
    Image.fromarray(res_arr).save(res_buf, format="PNG")
    result = res_buf.getvalue()

    metrics = _compute_quality_metrics(original, result, "#978B7B")
    assert metrics["quality_warning"] is True


def test_quality_metrics_aprova_imagem_boa():
    """Imagem identica com cor diferente nao deve ativar warning."""
    from app.services.color_variation import _compute_quality_metrics

    # Original
    orig_arr = np.zeros((100, 100, 4), dtype=np.uint8)
    orig_arr[50:, :, 0] = 100
    orig_arr[50:, :, 1] = 80
    orig_arr[50:, :, 2] = 70
    orig_arr[50:, :, 3] = 255
    # Textura
    for i in range(50, 100):
        for j in range(0, 100, 8):
            orig_arr[i, j:j+4, :3] = [130, 110, 100]

    orig_buf = io.BytesIO()
    Image.fromarray(orig_arr).save(orig_buf, format="PNG")
    original = orig_buf.getvalue()

    # Resultado: mesma textura, cor #978B7B (R=151, G=139, B=123)
    res_arr = orig_arr.copy()
    mask = orig_arr[:, :, 3] > 128
    res_arr[:, :, 0][mask] = (orig_arr[:, :, 0][mask].astype(float) * 151 / 100).clip(0, 255).astype(np.uint8)
    res_arr[:, :, 1][mask] = (orig_arr[:, :, 1][mask].astype(float) * 139 / 80).clip(0, 255).astype(np.uint8)
    res_arr[:, :, 2][mask] = (orig_arr[:, :, 2][mask].astype(float) * 123 / 70).clip(0, 255).astype(np.uint8)

    res_buf = io.BytesIO()
    Image.fromarray(res_arr).save(res_buf, format="PNG")
    result = res_buf.getvalue()

    metrics = _compute_quality_metrics(original, result, "#978B7B")
    assert metrics["quality_warning"] is False
    assert metrics["edge_correlation"] > 0.40


def test_pillow_fallback_cor_proxima_do_target():
    """Media RGB do resultado Pillow deve estar razoavel do target."""
    from app.services.color_variation import _apply_via_pillow
    from pathlib import Path
    import tempfile

    original = _make_rgba_image(200, 300, 120, 100, 90, transparent_pct=0.4)
    target = "#C8B8A0"  # R=200, G=184, B=160

    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test_color.png"
        result = _apply_via_pillow(original, target, output)

        assert output.exists()
        img = Image.open(output).convert("RGBA")
        arr = np.array(img)
        mask = arr[:, :, 3] > 128
        r_mean = arr[:, :, 0][mask].mean()
        g_mean = arr[:, :, 1][mask].mean()
        b_mean = arr[:, :, 2][mask].mean()

        # Cor deve estar num range razoavel (nao lavada nem invertida)
        assert r_mean > 100, f"R mean {r_mean} muito baixo"
        assert g_mean > 80, f"G mean {g_mean} muito baixo"


def test_pillow_fallback_preserva_alpha():
    """Pixels transparentes da original devem permanecer transparentes."""
    from app.services.color_variation import _apply_via_pillow
    from pathlib import Path
    import tempfile

    original = _make_rgba_image(200, 300, 120, 100, 90, transparent_pct=0.5)

    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test_alpha.png"
        _apply_via_pillow(original, "#C8B8A0", output)

        result = Image.open(output).convert("RGBA")
        arr = np.array(result)
        # Top half (transparent_pct=0.5) should remain transparent
        assert arr[:150, :, 3].max() == 0, "Transparent region was corrupted"
        # Bottom half should be opaque
        assert arr[150:, :, 3].min() == 255, "Garment alpha was corrupted"
