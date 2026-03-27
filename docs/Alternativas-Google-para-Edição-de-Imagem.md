# **Estratégias Avançadas de Edição de Imagem e Arquiteturas Multimodais no Ecossistema Google Cloud: Uma Análise Técnica e Estrutural**

O desenvolvimento de aplicações modernas de edição de imagens exige uma compreensão profunda da transição entre modelos de linguagem de grande escala e modelos multimodais nativos. O erro técnico identificado na tentativa de utilizar o modelo gemini-2.0-flash-exp com a configuração de response\_mime\_type: "image/png" evidencia um conflito fundamental na arquitetura de protocolos de comunicação de inteligência artificial generativa.1 Esta falha de protocolo HTTP 400 ocorre porque a interface de geração de conteúdo padrão do Gemini, baseada no método generateContent, foi projetada para retornar fluxos de tokens estruturados em texto ou formatos serializados como JSON e YAML, e não streams de pixels binários codificados como arquivos de imagem.2 Para superar este impasse e construir uma aplicação de edição de imagem resiliente e de alto desempenho, é necessário explorar as alternativas especializadas oferecidas pelo Google, especificamente a API Imagen 3 e os novos modelos multimodais da família Gemini através do SDK Google GenAI.4

## **A Crise dos Tipos MIME e a Necessidade de Especialização Arquitetural**

A análise da causa raiz do erro reportado revela que o sistema tentou forçar uma saída de imagem através de um duto projetado para texto. Na especificação técnica do Gemini 2.0 Flash, os tipos MIME permitidos para a configuração de geração são restritos a formatos que representam dados lógicos e não visuais.3 Ao definir manualmente um tipo de imagem para um modelo que, naquele endpoint específico, só processa texto, o servidor do Google Cloud invalida a requisição por inconformidade de esquema.1 Esta distinção é crucial para o desenvolvedor, pois sinaliza que a geração de imagens não é uma simples configuração de parâmetro, mas uma mudança de paradigma funcional dentro do Vertex AI e do Google AI Studio.8

A evolução das ferramentas de IA generativa no Google resultou em uma bifurcação técnica: de um lado, modelos de difusão puros como o Imagen 3, otimizados para manipulação de pixels em nível atômico; de outro, modelos multimodais nativos como o Gemini 2.5 e 3.1, que tratam imagens como modalidades equivalentes ao texto dentro de uma arquitetura de transformadores unificada.10 Para uma aplicação de edição, a escolha entre estas tecnologias depende da necessidade de precisão técnica baseada em máscaras ou flexibilidade conversacional baseada em linguagem natural.13

| Formato de Resposta Permitido | Descrição Técnica | Contexto de Uso no Gemini |
| :---- | :---- | :---- |
| text/plain | Texto sem formatação | Respostas padrão de chat e processamento simples. |
| application/json | Dados estruturados | Chamadas de função (Function Calling) e extração de entidades. |
| application/xml | Marcação estruturada | Integração com sistemas legados ou pipelines de dados. |
| application/yaml | Serialização legível | Configurações dinâmicas e definições de infraestrutura. |
| text/x.enum | Valores enumerados | Classificação estrita e seleção de opções predefinidas. |

A tabela acima ilustra os limites da interface GenerateContentRequest.2 A ausência de formatos de imagem como image/png ou image/jpeg nesta lista específica é o que desencadeia o fallback para bibliotecas locais como Pillow, conforme observado no comportamento do sistema do usuário.9

## **O Ecossistema Imagen 3: Domínio de Edição Baseada em Máscaras**

A alternativa mais robusta para funcionalidades de edição técnica — como inpainting, outpainting e substituição de fundo — reside na API dedicada do Imagen 3\. Ao contrário dos modelos Gemini, que processam a imagem através de um raciocínio textual subjacente, o Imagen opera diretamente no espaço latente da imagem, utilizando processos de difusão para preencher, expandir ou modificar áreas específicas com alta fidelidade fotográfica.15 O modelo de referência para estas tarefas é o imagen-3.0-capability-001, que se diferencia dos modelos de geração pura por sua capacidade de aceitar imagens de referência e máscaras de controle.17

### **Mecanismos de Inpainting e Inserção de Objetos**

O inpainting é o processo de editar o conteúdo dentro das fronteiras de uma imagem existente. No Vertex AI, isso é implementado através do modo EDIT\_MODE\_INPAINT\_INSERTION.17 Para que esta operação seja bem-sucedida, a aplicação deve fornecer ao modelo não apenas a imagem original, mas também uma máscara preta e branca onde os pixels brancos (valor não zero) indicam exatamente onde o modelo tem permissão para gerar novo conteúdo.18

O sistema oferece flexibilidade na criação de máscaras através de diferentes configurações de maskMode 17:

* **MASK\_MODE\_USER\_PROVIDED**: Permite que a aplicação envie uma máscara customizada, ideal para interfaces onde o usuário final desenha a área de edição com um pincel.17  
* **MASK\_MODE\_BACKGROUND**: Utiliza algoritmos de segmentação internos do Google para identificar e mascarar automaticamente o fundo, facilitando a substituição de cenários sem intervenção manual.17  
* **MASK\_MODE\_FOREGROUND**: Foca no objeto principal da imagem, permitindo alterações no assunto sem afetar o contexto.18  
* **MASK\_MODE\_SEMANTIC**: Uma funcionalidade avançada que utiliza modelos de visão computacional para isolar classes específicas de objetos (como carros, animais ou móveis) baseando-se em IDs de classe predefinidos.17

### **O Desafio Geométrico do Outpainting**

O outpainting, ou expansão de imagem, é uma das funcionalidades mais requisitadas para aplicações de design, permitindo alterar a proporção de uma foto (por exemplo, de 4:3 para 16:9) sem distorcer o conteúdo original.21 Tecnicamente, o outpainting é um caso especial de edição baseada em máscara onde o modelo preenche as áreas de padding adicionadas à imagem original.22

O processo exige uma preparação rigorosa dos dados de entrada. A imagem original deve ser colocada dentro de uma tela maior (canvas) e as novas áreas devem ser preenchidas com padding.22 Simultaneamente, deve ser gerada uma máscara que cubra exatamente essas novas áreas. O sucesso visual desta operação depende significativamente da dilatação da máscara (mask\_dilation). Recomenda-se um valor entre 1% e 3% (0.01 a 0.03) para que as bordas da máscara avancem ligeiramente sobre a imagem original, permitindo que o modelo "misture" os pixels novos com os antigos, evitando costuras visíveis.17

| Parâmetro Técnico | Valor Recomendado | Impacto na Qualidade |
| :---- | :---- | :---- |
| edit\_steps | 35 \- 75 | Define o número de iterações de difusão. Valores maiores aumentam o detalhamento, mas elevam a latência. |
| mask\_dilation | 0.01 \- 0.03 | Controla a suavidade da transição nas bordas da edição. |
| sample\_count | 1 \- 4 | Número de variações geradas. Útil para dar opções de escolha ao usuário. |
| guidance\_scale | 60 \- 75 | Força a fidelidade ao prompt. Valores excessivos podem causar artefatos cromáticos. |

## **Gemini Nano Banana: Geração Multimodal Nativa e Conversacional**

Enquanto o Imagen 3 se destaca pela precisão técnica, os novos modelos da série Gemini, conhecidos internamente pelos codinomes Nano Banana, oferecem uma abordagem radicalmente diferente baseada na multimodalidade nativa.12 Estes modelos, como o gemini-2.5-flash-image (Nano Banana) e o gemini-3.1-flash-image-preview (Nano Banana 2), são capazes de gerar imagens como parte de uma resposta de chat convencional.8

### **A Lógica das Modalidades de Resposta**

Para evitar o erro 400 de tipo MIME inválido, a integração com os modelos Gemini deve utilizar o parâmetro response\_modalities em vez de tentar configurar o cabeçalho de saída via response\_mime\_type.25 Ao definir response\_modalities:, o desenvolvedor instrui o modelo a retornar um objeto complexo que pode conter tanto strings de texto quanto blocos de dados binários de imagem intercalados.12

Esta arquitetura permite a "edição conversacional", onde o usuário pode enviar uma imagem e fornecer instruções em linguagem natural para modificá-la, como "mude a cor da camisa para azul" ou "adicione óculos escuros nesta pessoa".12 O modelo mantém o contexto histórico da conversa, permitindo refinamentos iterativos que seriam difíceis de implementar em um pipeline de API puramente técnico.13

### **Comparação de Modelos de Geração Nativa (Série Gemini 3\)**

| Modelo | Codinome | Posição de Mercado | Principais Diferenciais |
| :---- | :---- | :---- | :---- |
| gemini-3.1-flash-image-preview | Nano Banana 2 | Alta Eficiência | Proporções ultra-wide (8:1), baixa latência e aterramento via Google Search.24 |
| gemini-3-pro-image-preview | Nano Banana Pro | Produção Premium | Renderização de texto complexo em 4K e raciocínio avançado ("Thinking").10 |
| gemini-2.5-flash-image | Nano Banana | Legado Estável | Equilíbrio entre custo e velocidade para fluxos GA.23 |

O uso do aterramento (grounding) com o Google Search é um avanço significativo no Gemini 3.1 Flash Image. Ele permite que o modelo consulte imagens reais para garantir que representações de marcos históricos, marcas ou espécies biológicas sejam factualmente precisas, algo que os modelos de difusão tradicionais costumam falhar por dependerem exclusivamente de seus pesos de treinamento.27

## **Migração de SDK: Do google-generativeai para o google-genai**

Um fator determinante no erro enfrentado pelo usuário é a provável utilização de bibliotecas legadas. O Google introduziu o SDK google-genai (General Availability em maio de 2025\) como o sucessor oficial do google-generativeai.4 A migração para este novo SDK não é apenas uma mudança de nome, mas uma reestruturação da forma como os objetos de modelo e sessões de chat são gerenciados.4

No SDK antigo, o acesso era feito de forma ad hoc através de instâncias de GenerativeModel. No novo SDK, todas as interações são centralizadas em um objeto Client, que simplifica a transição entre ambientes de desenvolvimento (Google AI Studio) e produção (Enterprise Vertex AI).4 Esta centralização é vital para lidar com modalidades complexas, pois o cliente gerencia automaticamente o upload de arquivos e a serialização de dados multimodais que causaram a falha original no sistema do usuário.4

### **Mudanças Estruturais no Código Python**

A implementação correta para evitar erros de validação de argumentos exige o uso de classes Pydantic para configurações, garantindo que todos os parâmetros (como temperatura, top\_p e as modalidades de resposta) sejam validados antes do envio à rede.4

Python

\# Exemplo de implementação correta com o novo SDK google-genai  
from google import genai  
from google.genai import types

client \= genai.Client(api\_key="SUA\_CHAVE\_API")  
response \= client.models.generate\_content(  
    model="gemini-2.0-flash-exp",  
    contents=,  
    config=types.GenerateContentConfig(  
        response\_modalities= \# O segredo para evitar o erro 400  
    )  
)

Neste modelo, a imagem editada não é retornada como um erro de tipo MIME, mas sim como um objeto inline\_data dentro de uma das partes (Part) da resposta do candidato, que pode ser facilmente processada e salva localmente utilizando a biblioteca Pillow.9

## **Implementação Técnica: Helpers e Processamento de Imagem**

Para aplicações de edição, o processamento de imagem no lado do cliente (ou servidor de aplicação) continua sendo essencial para preparar os dados para os modelos de IA. O Google fornece utilitários específicos, especialmente dentro do SDK do Firebase AI Logic, para automatizar tarefas geométricas complexas.22

### **O Papel da Função generateMaskAndPadForOutpainting**

Uma das tarefas mais propensas a erro é o alinhamento de pixels entre a imagem original e a máscara de expansão. Se houver uma discrepância de apenas um pixel nas dimensões totais, o Vertex AI rejeitará a requisição com um erro de validação de dimensões.21 A função helper generateMaskAndPadForOutpainting resolve este problema ao:

1. Calcular as dimensões do novo canvas baseado na proporção alvo.22  
2. Posicionar a imagem original de acordo com a direção de expansão desejada (ex: CENTER, TOP\_CENTER, LEFT\_CENTER).22  
3. Gerar automaticamente uma imagem de máscara onde as novas áreas são brancas e a área da imagem original é preta.22  
4. Aplicar padding preto à imagem original para que ela coincida com o tamanho da máscara.22

Esta automação é crítica para garantir que o modelo imagen-3.0-capability-001 receba inputs matematicamente coerentes, o que aumenta drasticamente a taxa de sucesso das edições em massa.22

### **Requisitos de Codificação e Tamanho de Arquivo**

Independentemente do modelo escolhido, existem limites técnicos rigorosos que as aplicações devem observar para evitar erros de pré-condição (HTTP 400 FAILED\_PRECONDITION) 1:

* **Limite de Tamanho**: As imagens para edição via API REST ou SDK costumam ter um limite de 10 MB a 20 MB.5 Arquivos maiores devem ser redimensionados ou carregados via Google Cloud Storage (GCS).6  
* **Codificação Base64**: Para envios inline, as imagens devem ser convertidas em strings Base64 puras. Um erro comum é incluir o cabeçalho de data URI (ex: data:image/png;base64,...), que deve ser removido antes do envio.33  
* **Formatos Suportados**: PNG, JPEG, WEBP e HEIC são amplamente aceitos, mas PNG é preferível para máscaras devido à sua natureza sem perdas (lossless), o que evita artefatos de compressão que podem confundir o modelo.3

## **Arquitetura de Aplicação e Orquestração de Fluxos**

A construção de uma ferramenta de edição de nível profissional no Google Cloud vai além de uma simples chamada de API. Envolve a criação de uma arquitetura resiliente que orquestra vários serviços para garantir performance e escalabilidade.36

### **Padrões de Microserviços com Cloud Run e Workflows**

Para fluxos de trabalho que envolvem várias etapas (ex: Detecção de Objetos \-\> Geração de Máscara \-\> Inpainting \-\> Upscaling), o uso de **Cloud Workflows** é a estratégia recomendada. Ele permite encadear chamadas de API do Vertex AI com funções serverless personalizadas rodando no Cloud Run.38

Uma arquitetura de referência típica inclui:

1. **Cloud Storage**: Atua como o repositório central para ativos brutos e editados. O upload para o GCS dispara eventos via **Eventarc**.39  
2. **Cloud Vision API**: Utilizada para pré-processamento. Por exemplo, detectar se a imagem contém rostos para aplicar filtros de segurança automáticos ou extrair etiquetas que podem ser usadas para enriquecer o prompt de edição.37  
3. **Cloud Run com GPUs**: Para aplicações que necessitam de processamento de imagem local extremamente rápido antes do envio para a nuvem, o Cloud Run agora suporta aceleração por GPU (NVIDIA L4), permitindo rodar modelos de segmentação customizados ou bibliotecas como OpenCV em alta performance.41

### **O Protocolo de Contexto de Modelo (MCP) e Agentes de Edição**

Com a ascensão dos sistemas agentic, o **Model Context Protocol (MCP)** surge como um padrão para fornecer contexto externo a modelos multimodais.42 Em um cenário de edição de imagem para e-commerce, por exemplo, um agente de IA pode usar o MCP para consultar o banco de dados do BigQuery, obter detalhes técnicos de um produto e gerar um prompt de edição que substitua o fundo da imagem original por um cenário que esteja em conformidade com a campanha de marketing atual da marca.42 Esta integração transforma a edição de imagem de uma tarefa isolada em um processo de negócio inteligente e automatizado.

## **Análise Comparativa de Custos e Otimização Financeira**

A viabilidade econômica de uma aplicação de edição de imagem depende da escolha do modelo de precificação. O Google Cloud oferece dois modelos distintos: precificação baseada em tokens para a família Gemini e precificação fixa por imagem para a família Imagen.10

### **Modelos de Precificação (Estimativas de Março de 2026\)**

| Modelo | Tipo de Cobrança | Custo Estimado (1K res) | Janela de Otimização |
| :---- | :---- | :---- | :---- |
| **Imagen 4 Fast** | Por imagem gerada | $0.02 | Melhor custo-benefício para geração em massa.11 |
| **Imagen 4 Ultra** | Por imagem gerada | $0.06 | Ativos de alta qualidade com detalhes finos.11 |
| **Gemini 3.1 Flash Image** | Baseado em tokens | \~$0.04 \- $0.07 | Edição conversacional e fluxos de alta velocidade.11 |
| **Gemini 3 Pro Image** | Baseado em tokens | \~$0.13 \- $0.24 | Ativos premium, 4K e renderização de texto perfeita.28 |
| **Imagen Upscale API** | Por operação | $0.003 | Extrema economia para aumentar resolução de rascunhos.11 |

### **Estratégias de Redução de Gastos**

Uma das maiores oportunidades de economia reside na **Batch API**. Para tarefas que não exigem interatividade em tempo real — como o processamento noturno de milhares de fotos de produtos — o Google aplica um desconto de 50% sobre os preços de tabela de tokens para modelos Gemini.10 Isso reduz o custo do Gemini 2.5 Flash de $0.039 para menos de $0.02 por imagem, tornando-o competitivo até com os modelos mais básicos.10

Outra tática essencial é o roteamento híbrido:

1. Utilizar modelos Flash ou Imagen Fast para gerar rascunhos e permitir que o usuário itere rapidamente.11  
2. Somente quando o usuário aprovar o rascunho, enviar o prompt final para o Gemini 3 Pro Image ou Imagen 4 Ultra para a renderização definitiva.10  
3. Integrar a API de Upscaling dedicada ($0.003) em vez de gerar nativamente em 4K desde o início, o que pode custar até 80 vezes mais em tokens de saída.11

## **Segurança, Ética e Integridade Visual**

A implantação de ferramentas de edição de imagem em ambientes corporativos exige conformidade com diretrizes de IA responsável. O Google implementa várias camadas de proteção que podem impactar o desenvolvimento.46

### **Filtros de Segurança e Geração de Pessoas**

Os modelos Imagen 3 e 4 permitem o controle granular sobre a geração de seres humanos. O parâmetro person\_generation suporta valores como dont\_allow (proíbe faces humanas), allow\_adult (restringe a adultos) e allow\_all.17 Além disso, o safety\_filter\_level permite ajustar a sensibilidade do bloqueio de conteúdo ofensivo, variando de BLOCK\_LOW\_AND\_ABOVE (máxima segurança) a BLOCK\_ONLY\_HIGH (mais liberdade criativa, maior risco).17 É fundamental que a aplicação trate os cenários onde o modelo se recusa a editar uma imagem devido a estes filtros, retornando mensagens claras ao usuário final em vez de falhas genéricas de sistema.1

### **SynthID e Content Credentials (C2PA)**

Para combater a desinformação e proteger os direitos autorais, todas as imagens geradas ou editadas pelos modelos de ponta do Google incluem o **SynthID**.15 Esta é uma marca d'água digital invisível incorporada diretamente nos pixels, resistente a cortes, edições comuns e filtros. Além disso, os modelos mais recentes como o Imagen 3 e o Gemini 3.1 suportam o padrão **C2PA (Coalition for Content Provenance and Authenticity)**, que anexa metadados criptográficos à imagem para rastrear sua origem e as ferramentas de IA utilizadas em sua criação.5

## **Ciclo de Vida dos Modelos e Planejamento de Longo Prazo**

O desenvolvedor deve estar atento às datas de encerramento (shutdown) dos modelos no Vertex AI para evitar interrupções de serviço. Muitos modelos experimentais e versões específicas da série 2.0 têm encerramento previsto para o primeiro semestre de 2026\.48

| Modelo Atual | Recomendação de Migração | Data Limite Estimada |
| :---- | :---- | :---- |
| gemini-2.0-flash-exp | gemini-2.5-flash ou gemini-3.1-flash | Junho de 2026 3 |
| imagegeneration@006 | gemini-2.5-flash-image | Junho de 2026 5 |
| imagen-product-recontext | gemini-2.5-flash-image | Março de 2026 50 |

A recomendação geral é migrar o quanto antes para as versões estáveis (GA) e utilizar aliases de modelo (ex: gemini-2.5-flash) em vez de IDs de versão fixos, permitindo que o Google atualize o backend automaticamente para a versão mais recente e segura sem necessidade de deploy de novo código.51

## **Conclusões e Recomendações para a Aplicação do Usuário**

Com base na análise do erro reportado e na pesquisa de alternativas atualizadas, as seguintes conclusões e recomendações técnicas são apresentadas para a evolução da aplicação de edição de imagens:

A falha original de tipo MIME deve ser resolvida abandonando o SDK google-generativeai em favor do google-genai. A configuração de geração deve ser ajustada para incluir explicitamente a modalidade de imagem (response\_modalities=), eliminando a necessidade de forçar tipos de arquivo nos cabeçalhos de requisição de texto.4

Para fluxos de trabalho que exigem precisão geométrica e controle absoluto sobre áreas de edição (como inpainting e outpainting em larga escala), o modelo imagen-3.0-capability-001 continua sendo a ferramenta superior devido aos seus parâmetros dedicados de máscara e dilatação.17 Para interfaces voltadas ao usuário final que priorizam a facilidade de uso e comandos naturais, os modelos Gemini Nano Banana (2.5 e 3.1 Flash Image) oferecem uma experiência conversacional mais intuitiva e integrada.12

A implementação deve incorporar funções auxiliares para o processamento de padding e máscaras, garantindo a integridade dimensional dos dados enviados ao Vertex AI.22 Além disso, uma estratégia de precificação baseada no uso de Upscaling e processamento em lote (Batch API) pode reduzir drasticamente os custos operacionais da plataforma em produção.10

Por fim, a conformidade com padrões de segurança e proveniência (SynthID e C2PA) não deve ser vista apenas como um requisito técnico, mas como um diferencial de mercado que garante a integridade e a confiança nas mídias geradas pela aplicação.5 A integração dessas tecnologias posiciona a aplicação na vanguarda da edição de mídia visual, aproveitando o máximo das capacidades multimodais oferecidas pelo Google Cloud em 2026\.

#### **Referências citadas**

1. Troubleshooting guide | Gemini API \- Google AI for Developers, acessado em março 26, 2026, [https://ai.google.dev/gemini-api/docs/troubleshooting](https://ai.google.dev/gemini-api/docs/troubleshooting)  
2. Types for Google Ai Generativelanguage v1alpha API, acessado em março 26, 2026, [https://googleapis.dev/python/generativelanguage/latest/generativelanguage\_v1alpha/types\_.html](https://googleapis.dev/python/generativelanguage/latest/generativelanguage_v1alpha/types_.html)  
3. Gemini 2.0 Flash | Generative AI on Vertex AI \- Google Cloud Documentation, acessado em março 26, 2026, [https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-0-flash](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-0-flash)  
4. Migrate to the Google GenAI SDK | Gemini API, acessado em março 26, 2026, [https://ai.google.dev/gemini-api/docs/migrate](https://ai.google.dev/gemini-api/docs/migrate)  
5. Imagen 3 | Generative AI on Vertex AI \- Google Cloud Documentation, acessado em março 26, 2026, [https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/imagen/3-0-generate](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/imagen/3-0-generate)  
6. Generate content with the Gemini API in Vertex AI \- Google Cloud Documentation, acessado em março 26, 2026, [https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/inference](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/inference)  
7. Generative AI on Vertex AI inference API errors \- Google Cloud Documentation, acessado em março 26, 2026, [https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/api-errors](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/api-errors)  
8. Detecting and Editing Visual Objects with Gemini | Towards Data Science, acessado em março 26, 2026, [https://towardsdatascience.com/detecting-and-editing-visual-objects-with-gemini/](https://towardsdatascience.com/detecting-and-editing-visual-objects-with-gemini/)  
9. Generating images with Gemini 2.0 Flash \- DEV Community, acessado em março 26, 2026, [https://dev.to/gde/generating-images-with-gemini-20-flash-from-google-448e](https://dev.to/gde/generating-images-with-gemini-20-flash-from-google-448e)  
10. Cheap Gemini Image API: Complete 2026 Pricing Guide (Save Up to 80%), acessado em março 26, 2026, [https://blog.laozhang.ai/en/posts/cheap-gemini-image-api](https://blog.laozhang.ai/en/posts/cheap-gemini-image-api)  
11. Cheapest Gemini Image API in 2026: Save 85%+ with These 5 Proven Strategies, acessado em março 26, 2026, [https://blog.laozhang.ai/en/posts/gemini-image-cheapest-api-2026](https://blog.laozhang.ai/en/posts/gemini-image-cheapest-api-2026)  
12. Experiment with Gemini 2.0 Flash native image generation \- Google Developers Blog, acessado em março 26, 2026, [https://developers.googleblog.com/experiment-with-gemini-20-flash-native-image-generation/](https://developers.googleblog.com/experiment-with-gemini-20-flash-native-image-generation/)  
13. Generative Images with Gemini (New Updates) \- Raymond Camden, acessado em março 26, 2026, [https://www.raymondcamden.com/2025/03/14/generative-images-with-gemini-new-updates](https://www.raymondcamden.com/2025/03/14/generative-images-with-gemini-new-updates)  
14. gemini-2.0-flash-exp | AI/ML API Documentation, acessado em março 26, 2026, [https://docs.aimlapi.com/api-references/text-models-llm/google/gemini-2.0-flash-exp](https://docs.aimlapi.com/api-references/text-models-llm/google/gemini-2.0-flash-exp)  
15. What Is Imagen 3? Google's Photorealistic AI Image Generator | MindStudio, acessado em março 26, 2026, [https://www.mindstudio.ai/blog/what-is-imagen-3-google-photorealistic](https://www.mindstudio.ai/blog/what-is-imagen-3-google-photorealistic)  
16. generative-ai/vision/getting-started/imagen3\_editing.ipynb at main \- GitHub, acessado em março 26, 2026, [https://github.com/GoogleCloudPlatform/generative-ai/blob/main/vision/getting-started/imagen3\_editing.ipynb](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/vision/getting-started/imagen3_editing.ipynb)  
17. Edit images | Generative AI on Vertex AI \- Google Cloud Documentation, acessado em março 26, 2026, [https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/imagen-api-edit](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/imagen-api-edit)  
18. Insert objects into an image using inpaint | Generative AI on Vertex AI, acessado em março 26, 2026, [https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/edit-insert-objects](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/edit-insert-objects)  
19. Imagen \- Google Gen AI Python SDK \- Mintlify, acessado em março 26, 2026, [https://mintlify.com/googleapis/python-genai/guides/imagen](https://mintlify.com/googleapis/python-genai/guides/imagen)  
20. Mastering Image Editing with Imagen 3 on Google Cloud | by Simon Lee | Medium, acessado em março 26, 2026, [https://simonleewm.medium.com/mastering-image-editing-with-imagen-3-on-google-cloud-95361c150626](https://simonleewm.medium.com/mastering-image-editing-with-imagen-3-on-google-cloud-95361c150626)  
21. Expand the content of an image using outpaint | Generative AI on Vertex AI, acessado em março 26, 2026, [https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/edit-outpainting](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/edit-outpainting)  
22. Expand the content of an image using outpainting with Imagen | Firebase AI Logic \- Google, acessado em março 26, 2026, [https://firebase.google.com/docs/ai-logic/edit-images-imagen-expand-images](https://firebase.google.com/docs/ai-logic/edit-images-imagen-expand-images)  
23. Nano Banana image generation \- Gemini API | Google AI for Developers, acessado em março 26, 2026, [https://ai.google.dev/gemini-api/docs/image-generation](https://ai.google.dev/gemini-api/docs/image-generation)  
24. Nano Banana 2 Development Documentation Complete Guide: Comparison of Official API and APIYI Integration Solutions, acessado em março 26, 2026, [https://help.apiyi.com/en/nano-banana-2-developer-docs-api-guide-en.html](https://help.apiyi.com/en/nano-banana-2-developer-docs-api-guide-en.html)  
25. A Practical Guide to Image-to-Image AI with Gemini 2.0 Flash | by Gabriel Preda | Medium, acessado em março 26, 2026, [https://medium.com/@gabi.preda/this-ai-bot-turned-my-vibe-into-visuals-thanks-gemini-64b4046288cb](https://medium.com/@gabi.preda/this-ai-bot-turned-my-vibe-into-visuals-thanks-gemini-64b4046288cb)  
26. Gemini 2.0 Flash: Unleashing Native Image Generation — A Tech Deep Dive \- Medium, acessado em março 26, 2026, [https://medium.com/@chongcht/gemini-2-0-flash-unleashing-native-image-generation-a-tech-deep-dive-85026fcd0f77](https://medium.com/@chongcht/gemini-2-0-flash-unleashing-native-image-generation-a-tech-deep-dive-85026fcd0f77)  
27. Gemini 3.1 Flash Image (Nano Banana 2\) \- Google AI Studio, acessado em março 26, 2026, [https://aistudio.google.com/models/gemini-3-1-flash-image](https://aistudio.google.com/models/gemini-3-1-flash-image)  
28. Gemini Image Generation Cost Calculator: Official API Prices by Model, acessado em março 26, 2026, [https://www.aifreeapi.com/en/posts/gemini-image-generation-api-pricing](https://www.aifreeapi.com/en/posts/gemini-image-generation-api-pricing)  
29. Google models | Generative AI on Vertex AI, acessado em março 26, 2026, [https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models)  
30. Ultimate prompting guide for Nano Banana | Google Cloud Blog, acessado em março 26, 2026, [https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana)  
31. Gemini API libraries \- Google AI for Developers, acessado em março 26, 2026, [https://ai.google.dev/gemini-api/docs/libraries](https://ai.google.dev/gemini-api/docs/libraries)  
32. gemini-3-pro-image (Nano Banana 2\) \- UCloud Global, acessado em março 26, 2026, [https://www.ucloud-global.com/en/docs/modelverse/modelverse/image\_api/gemini-3-pro-image](https://www.ucloud-global.com/en/docs/modelverse/modelverse/image_api/gemini-3-pro-image)  
33. Error when trying to upload an image prompt to gemini api \- Stack Overflow, acessado em março 26, 2026, [https://stackoverflow.com/questions/78754268/error-when-trying-to-upload-an-image-prompt-to-gemini-api](https://stackoverflow.com/questions/78754268/error-when-trying-to-upload-an-image-prompt-to-gemini-api)  
34. Gemini API Error 400: Invalid or Unsupported File URI \- Stack Overflow, acessado em março 26, 2026, [https://stackoverflow.com/questions/78909501/gemini-api-error-400-invalid-or-unsupported-file-uri](https://stackoverflow.com/questions/78909501/gemini-api-error-400-invalid-or-unsupported-file-uri)  
35. Image understanding | Generative AI on Vertex AI \- Google Cloud Documentation, acessado em março 26, 2026, [https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/image-understanding](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/image-understanding)  
36. Cloud Architecture Guidance and Topologies | Cloud Architecture Center | Google Cloud Documentation, acessado em março 26, 2026, [https://docs.cloud.google.com/architecture](https://docs.cloud.google.com/architecture)  
37. Vision AI: Image and visual AI tools | Google Cloud, acessado em março 26, 2026, [https://cloud.google.com/vision](https://cloud.google.com/vision)  
38. Workflows documentation \- Google Cloud Documentation, acessado em março 26, 2026, [https://docs.cloud.google.com/workflows/docs](https://docs.cloud.google.com/workflows/docs)  
39. Deploy an AI application that harnesses the power of LLMs \- Google Cloud, acessado em março 26, 2026, [https://cloud.google.com/solutions/generative-ai](https://cloud.google.com/solutions/generative-ai)  
40. Large Language Models (LLMs) with Google AI, acessado em março 26, 2026, [https://cloud.google.com/ai/llms](https://cloud.google.com/ai/llms)  
41. AI/ML orchestration on Cloud Run documentation, acessado em março 26, 2026, [https://docs.cloud.google.com/run/docs/ai](https://docs.cloud.google.com/run/docs/ai)  
42. Building Scalable AI Agents: Design Patterns With Agent Engine On Google Cloud, acessado em março 26, 2026, [https://cloud.google.com/blog/topics/partners/building-scalable-ai-agents-design-patterns-with-agent-engine-on-google-cloud](https://cloud.google.com/blog/topics/partners/building-scalable-ai-agents-design-patterns-with-agent-engine-on-google-cloud)  
43. AI Image Pricing 2026: Google Gemini vs. OpenAI GPT Cost Analysis | IntuitionLabs, acessado em março 26, 2026, [https://intuitionlabs.ai/articles/ai-image-generation-pricing-google-openai](https://intuitionlabs.ai/articles/ai-image-generation-pricing-google-openai)  
44. Vertex AI Pricing | Google Cloud, acessado em março 26, 2026, [https://cloud.google.com/vertex-ai/generative-ai/pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)  
45. AI Image Generation 2026: GPT Image 1.5, Gem… \- Till Freitag, acessado em março 26, 2026, [https://till-freitag.com/en/blog/ai-image-generation-models-2026](https://till-freitag.com/en/blog/ai-image-generation-models-2026)  
46. Image generation API \- Vertex AI \- Google Cloud Documentation, acessado em março 26, 2026, [https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/imagen-api](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/imagen-api)  
47. How to Implement Image Generation with Imagen on Vertex AI \- OneUptime, acessado em março 26, 2026, [https://oneuptime.com/blog/post/2026-02-17-how-to-implement-image-generation-with-imagen-on-vertex-ai/view](https://oneuptime.com/blog/post/2026-02-17-how-to-implement-image-generation-with-imagen-on-vertex-ai/view)  
48. Imagen 4 | Generative AI on Vertex AI \- Google Cloud Documentation, acessado em março 26, 2026, [https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/imagen/4-0-generate](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/imagen/4-0-generate)  
49. Release notes | Gemini API \- Google AI for Developers, acessado em março 26, 2026, [https://ai.google.dev/gemini-api/docs/changelog](https://ai.google.dev/gemini-api/docs/changelog)  
50. Imagen product recontext on Vertex AI \- Google Cloud Documentation, acessado em março 26, 2026, [https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/imagen/product-recontext-preview-06-30](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/imagen/product-recontext-preview-06-30)  
51. Model versions and lifecycle | Generative AI on Vertex AI \- Google Cloud Documentation, acessado em março 26, 2026, [https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions)