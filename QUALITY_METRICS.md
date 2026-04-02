# Como Funciona a Verificacao de Qualidade das Variacoes de Cor

## Visao Geral

Apos cada geracao de variacao de cor (via Gemini ou Pillow), o sistema executa automaticamente uma funcao que **compara a imagem gerada com a imagem original** e calcula duas metricas numericas. Se os numeros indicam resultado ruim, um badge "Qualidade baixa" aparece no card.

O codigo fica em `backend/app/services/color_variation.py`, funcao `_compute_quality_metrics`.

---

## O Codigo Completo — Comentado Linha a Linha

```python
def _compute_quality_metrics(original_bytes: bytes, result_bytes: bytes, target_hex: str) -> dict:
```

A funcao recebe tres parametros:
- `original_bytes` — os bytes da imagem PNG original que o operador enviou (a peca real)
- `result_bytes` — os bytes da imagem PNG gerada pela IA (o resultado da variacao de cor)
- `target_hex` — a cor alvo que foi solicitada, ex: `"#978B7B"`

---

### Passo 1 — Carregar as duas imagens como arrays de pixels

```python
    original = Image.open(io.BytesIO(original_bytes)).convert("RGBA")
    result = Image.open(io.BytesIO(result_bytes)).convert("RGBA")
```

Abre as duas imagens e converte para o modo RGBA (Red, Green, Blue, Alpha).
O canal Alpha (A) indica transparencia: 0 = totalmente transparente, 255 = totalmente opaco.

```python
    if result.size != original.size:
        result = result.resize(original.size, Image.LANCZOS)
```

Se o Gemini retornou a imagem em resolucao diferente da original (ex: 864x1184 vs 1414x2000),
redimensiona o resultado para o tamanho da original. Sem isso, nao da para comparar pixel a pixel.
`LANCZOS` e um algoritmo de interpolacao de alta qualidade que minimiza perda visual no resize.

```python
    orig_arr = np.array(original)    # shape: (altura, largura, 4) — cada pixel = [R, G, B, A]
    result_arr = np.array(result)    # mesma shape
```

Converte as imagens PIL para arrays NumPy. Cada pixel vira um vetor de 4 numeros (0-255).
Exemplo: o pixel na posicao (100, 200) da original seria `orig_arr[100, 200]` = `[142, 87, 63, 255]`.

---

### Passo 2 — Criar a mascara da roupa

```python
    mask = orig_arr[:, :, 3] > 128
```

**Esta e a linha mais importante para entender todo o resto.**

`orig_arr[:, :, 3]` pega APENAS o canal Alpha de todos os pixels da imagem original.
O resultado e uma matriz 2D (altura x largura) onde cada valor e o alpha daquele pixel.

`> 128` transforma em uma matriz booleana:
- `True` = pixel da roupa (opaco, alpha > 128)
- `False` = pixel do fundo (transparente, alpha <= 128)

Isso nos permite ignorar o fundo da imagem e analisar APENAS os pixels que pertencem a peca de roupa.

Visualizacao:
```
Imagem original:          Mascara (mask):
+-------------------+     +-------------------+
|  fundo  |  roupa  |     | False  |  True    |
| (alpha  | (alpha  |     | False  |  True    |
|  = 0)   | = 255)  |     | False  |  True    |
+-------------------+     +-------------------+
```

```python
    if not mask.any():
        return {"edge_correlation": 0.0, "color_distance": 999.0, "quality_warning": True}
```

Se nao existe nenhum pixel opaco (a imagem inteira e transparente), retorna metricas ruins
e ativa o warning. Isso nunca deveria acontecer, mas e uma protecao defensiva.

---

### Passo 3 — Metrica 1: Correlacao de Bordas (edge_correlation)

**Objetivo:** Medir se a IA preservou os detalhes estruturais da peca — costuras, pregas, botoes, textura do tecido.

#### 3a. Converter para escala de cinza

```python
    orig_gray = Image.fromarray(
        (0.299 * orig_arr[:, :, 0] + 0.587 * orig_arr[:, :, 1] + 0.114 * orig_arr[:, :, 2]).astype(np.uint8)
    )
    result_gray = Image.fromarray(
        (0.299 * result_arr[:, :, 0] + 0.587 * result_arr[:, :, 1] + 0.114 * result_arr[:, :, 2]).astype(np.uint8)
    )
```

Converte ambas as imagens para escala de cinza usando a formula padrao ITU-R BT.601:
```
Luminancia = 0.299 * R + 0.587 * G + 0.114 * B
```

Por que esses pesos? O olho humano e mais sensivel ao verde (0.587) do que ao vermelho (0.299) ou azul (0.114). Esta formula produz um cinza que corresponde ao brilho percebido pelo olho.

**Por que converter para cinza?** Porque queremos comparar a ESTRUTURA (bordas, formas), nao a COR. Removendo a cor, focamos puramente em onde estao as transicoes de luz/sombra.

#### 3b. Detectar bordas

```python
    orig_edges = np.array(orig_gray.filter(ImageFilter.FIND_EDGES))
    result_edges = np.array(result_gray.filter(ImageFilter.FIND_EDGES))
```

Aplica o filtro FIND_EDGES do Pillow. Este filtro usa um kernel de convolucao 3x3:
```
Kernel:
| -1 | -1 | -1 |
| -1 |  8 | -1 |
| -1 | -1 | -1 |
```

Para cada pixel, o filtro multiplica os 8 vizinhos por -1 e o pixel central por 8, depois soma.
- Se todos os vizinhos tem valor similar ao central: resultado proximo de 0 (area uniforme)
- Se ha contraste forte (uma borda): resultado alto (valor > 0)

O resultado e uma imagem onde:
- Pixels brilhantes = bordas (costuras, dobras, transicoes de tecido)
- Pixels escuros = areas uniformes (superficies lisas do tecido)

Visualizacao:
```
Imagem cinza:             Apos FIND_EDGES:
+-------------------+     +-------------------+
| ██████████ textura|     |          linhas   |
| ██ costura ██████ |     | ██ borda forte ██ |
| ██████████████████|     |                   |
+-------------------+     +-------------------+
```

#### 3c. Calcular correlacao

```python
    oe = orig_edges[mask].astype(float)    # bordas da original, APENAS pixels da roupa
    re = result_edges[mask].astype(float)  # bordas do resultado, APENAS pixels da roupa
    edge_correlation = float(np.corrcoef(oe, re)[0, 1])
```

`orig_edges[mask]` usa a mascara booleana para selecionar APENAS os pixels da roupa no mapa de bordas. Isso retorna um vetor 1D (lista plana) com os valores de borda de cada pixel.

`np.corrcoef(oe, re)` calcula o **coeficiente de correlacao de Pearson** entre os dois vetores.

**O que e correlacao de Pearson?**

Mede o quanto duas series de numeros "andam juntas":
- **1.0** = correlacao perfeita — onde a original tem borda forte, o resultado tambem tem
- **0.5** = correlacao moderada — algumas bordas coincidem, outras nao
- **0.0** = nenhuma correlacao — as bordas estao em lugares completamente diferentes
- **-1.0** = correlacao inversa — onde a original tem borda, o resultado nao tem (e vice-versa)

**Interpretacao para nosso caso:**
- `> 0.50` = mesma peca, detalhes preservados (costuras, pregas no mesmo lugar)
- `0.10 - 0.50` = peca similar mas com detalhes diferentes (Gemini gerou nova)
- `< 0.05` = imagem completamente diferente — warning ativado

**Exemplo numerico simplificado:**
```
Original (bordas):   [0, 0, 200, 180, 0, 0, 150, 0]   ← costura na posicao 2-3, prega na posicao 6
Resultado bom:       [0, 0, 190, 170, 0, 0, 140, 0]   ← mesmas posicoes → correlacao ~0.98
Resultado Gemini:    [0, 150, 0, 0, 180, 0, 0, 100]   ← bordas em posicoes diferentes → correlacao ~0.11
Resultado horrivel:  [0, 0, 0, 0, 0, 0, 0, 0]          ← sem bordas → correlacao ~0.0
```

---

### Passo 4 — Metrica 2: Distancia de Cor (color_distance)

**Objetivo:** Medir o quanto a cor do resultado se aproximou da cor solicitada.

#### 4a. Decodificar a cor alvo

```python
    target_r = int(target_hex[1:3], 16)    # "#978B7B" → "97" → 151
    target_g = int(target_hex[3:5], 16)    # "#978B7B" → "8B" → 139
    target_b = int(target_hex[5:7], 16)    # "#978B7B" → "7B" → 123
```

Converte o hex para valores RGB (0-255).
`int("97", 16)` converte o hexadecimal "97" para decimal 151.

#### 4b. Calcular a cor media do resultado

```python
    result_r = float(result_arr[:, :, 0][mask].mean())   # media do canal R de todos os pixels da roupa
    result_g = float(result_arr[:, :, 1][mask].mean())   # media do canal G
    result_b = float(result_arr[:, :, 2][mask].mean())   # media do canal B
```

`result_arr[:, :, 0]` pega o canal vermelho de todos os pixels.
`[mask]` filtra apenas os pixels da roupa.
`.mean()` calcula a media aritmetica.

Se o resultado tem 500.000 pixels de roupa, esta calculando a media dos 500.000 valores de cada canal.

#### 4c. Calcular a distancia euclidiana

```python
    color_distance = ((result_r - target_r)**2 + (result_g - target_g)**2 + (result_b - target_b)**2) ** 0.5
```

Formula da distancia euclidiana no espaco RGB tridimensional:
```
distancia = sqrt( (R_resultado - R_alvo)^2 + (G_resultado - G_alvo)^2 + (B_resultado - B_alvo)^2 )
```

Imagine as cores como pontos num cubo 3D (R, G, B). A distancia e a "linha reta" entre a cor alvo e a cor media do resultado.

**Exemplos:**
```
Alvo: #978B7B = (151, 139, 123)

Resultado perfeito:  (151, 139, 123) → distancia = 0.0
Resultado aceitavel: (138, 127, 112) → distancia = 22.5
Resultado ruim:      (77, 66, 57)    → distancia = 113.4
Resultado horrivel:  (10, 10, 10)    → distancia = 226.8
```

- `< 50` = cor muito proxima do alvo
- `50 - 100` = cor no tom certo mas com desvio
- `100 - 150` = cor notavelmente diferente
- `> 150` = cor completamente errada — warning ativado

---

### Passo 5 — Montar o resultado e decidir o warning

```python
    return {
        "edge_correlation": round(edge_correlation, 4),    # ex: 0.4752
        "color_distance": round(color_distance, 1),        # ex: 35.3
        "target_hex": target_hex,                          # ex: "#978B7B"
        "result_mean_rgb": [round(result_r), round(result_g), round(result_b)],  # ex: [138, 127, 112]
        "quality_warning": edge_correlation < 0.05 or color_distance > 150,
    }
```

O `quality_warning` e `True` se QUALQUER condicao for verdadeira:
- `edge_correlation < 0.05` = a peca gerada nao tem NADA a ver com a original
- `color_distance > 150` = a cor ficou completamente errada

Quando `quality_warning = True`, o frontend exibe o badge "Qualidade baixa" no card.

---

## Fluxo Completo — Da Geracao ao Badge

```
1. Operador clica "Executar pipeline" com cores #696980, #978B7B, #9E987D
                    |
2. Backend envia imagem ao Gemini com prompt de recoloracao
                    |
3. Gemini retorna imagem nova
                    |
4. _restore_alpha() restaura transparencia e resolucao da original
                    |
5. _compute_quality_metrics() compara original vs resultado:
   |
   |── edge_correlation = 0.48  (bordas parcialmente preservadas)
   |── color_distance = 35.3    (cor proxima do alvo)
   |── quality_warning = False  (ambos acima dos limiares)
                    |
6. Resultado salvo no banco com quality_metrics no JSON
                    |
7. Frontend le job.result.quality_metrics.quality_warning
   |
   |── Se True  → mostra badge "Qualidade baixa" no card
   |── Se False → nao mostra nada (resultado aceitavel)
```

---

## Onde Cada Parte Vive no Codigo

| O que | Arquivo | Linha |
|---|---|---|
| Funcao de metricas | `backend/app/services/color_variation.py` | 76-126 |
| Chamada pos-Gemini | `backend/app/services/color_variation.py` | 200 |
| Salvamento no banco | `backend/app/api/jobs.py` | 196 |
| Badge no frontend | `frontend/src/pages/Resultados.jsx` | 486-490 |
