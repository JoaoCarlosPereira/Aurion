# Design System - Pacman Tech Theme

Template reutilizavel para portifolios e sites pessoais com estilo tecnologico e arcadico.

## 1. Visao Geral

Site estatico de pagina pessoal baseado no template **Start Bootstrap - Personal v1.0.1**, adaptado com tema visual proprio inspirado em arcade (Pac-Man). Construido com HTML5, CSS3 e JavaScript vanilla, sobre o Bootstrap 5.2.3.

### Estrutura de arquivos

```
design/
├── css/
│   ├── styles.css            -> Estilos principais (Bootstrap + custom)
│   └── responsive-fixes.css  -> Ajustes responsivos cross-page
├── js/
│   ├── scripts.js            -> Background animado Pac-Man
│   ├── miriam-widget.js      -> Widget de assistente
│   ├── i18n.js               -> Internacionalizacao
│   ├── arcade.js             -> Jogos arcadicos opcionais
│   └── snake.js              -> Jogo Snake opcional
├── assets/
│   ├── profile.png           -> Foto de perfil
│   └── favicon.ico           -> Favicon
├── index.html                -> Homepage
├── resume.html               -> Sobre / carreira
├── projects.html             -> Formacoes academicas
├── contact.html              -> Cartao de contato
├── miriam-ai.html            -> Pagina de embed de assistente AI
├── diversao.html             -> Pagina de conteudo opcional
└── design.md                 -> Este documento
```

### Usando o Design em Outro Projeto

Para reutilizar este design em outro projeto, copie toda a pasta `design/` e renomeie conforme necessario. Os caminhos relativos entre os arquivos (CSS, JS, HTML, assets) ja estao configurados para funcionar dentro da estrutura `design/`.

### Dependencias externas

| Recurso | Versao | Fonte |
|---|---|---|
| Bootstrap | 5.2.3 | cdnjs.cloudflare.com / jsdelivr |
| Bootstrap Icons | 1.8.1 | cdn.jsdelivr.net |
| Google Fonts - Plus Jakarta Sans | Todos os pesos (100-900) | fonts.googleapis.com |

### Dependencias JavaScript

| Recurso | Responsabilidade |
|---|---|
| bootstrap.bundle.min.js | Dropdowns, collapse de navbar, utilidades |
| scripts.js | Canvas animado Pac-Man com fundo interativo |
| miriam-widget.js | Widget de assistente AI integrado |
| i18n.js | Traducao de conteudo multilenguagem |

## 2. Paleta de Cores

### Cores principais

| Variavel | Hex | RGB | Uso |
|---|---|---|---|
| `--bs-primary` | #1e30f3 | 30, 48, 243 | Azul primario - botões, links, acoes |
| `--bs-secondary` | #e21e80 | 226, 30, 128 | Rosa secundario - gradientes, destaques |
| `--bs-dark` | #212529 | 33, 37, 41 | Texto principal |
| `--bs-light` | #f8f9fa | 248, 249, 250 | Fundos alternativos, seções claras |
| `--bs-body-bg` | #ffffff | 255, 255, 255 | Fundo principal (branco) |

### Gradientes

**Primario para Secundario** (botões, badges, elementos de destaque):

```css
linear-gradient(135deg, #1e30f3 0%, #e21e80 100%)
```

**Texto Gradiente** (titulos com efeito degradê):

```css
linear-gradient(315deg, #1e30f3 0%, #e21e80 100%)
```

Aplicado via `-webkit-background-clip: text` com `-webkit-text-fill-color: transparent`.

### Cores semânticas Bootstrap

| Cor | Hex | Uso |
|---|---|---|
| Success | #198754 | Confirmacoes, estados positivos |
| Info | #0dcaf0 | Informacoes, destaques neutros |
| Warning | #ffc107 | Alertas, avisos |
| Danger | #dc3545 | Erros, alertas criticos |

### Cores do tema Pac-Man

| Elemento | Cor | Hex |
|---|---|---|
| Pac-Man | Amarelo | #ffd166 |
| Ghost 1 | Rosa claro | #ff4d6d |
| Ghost 2 | Ciano | #34d3ff |
| Ghost 3 | Amarelo escuro | #ffb703 |
| Ghost 4 | Roxo | #b582ff |
| Ghost 5 | Turquesa | #00f5d4 |

## 3. Tipografia

### Fonte principal

**Plus Jakarta Sans** - Google Fonts. Pesos: 100, 200, 300, 400, 500, 600, 700, 800, 900.

```html
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@100;200;300;400;500;600;700;800;900&display=swap" rel="stylesheet" />
```

### Escala tipografica

| Elemento | Tamanho base | Peso | Linha |
|---|---|---|---|
| h1 / display-1 | 2.5rem (calc com vw) | 300 | 1.2 |
| h2 / display-2 | 2rem (calc com vw) | 300 | 1.2 |
| h3 / display-3 | 1.75rem (calc com vw) | 300 | 1.2 |
| h4 / display-4 | 1.5rem (calc com vw) | 300 | 1.2 |
| h5 / display-5 | 1.25rem | 500 | 1.2 |
| h6 / display-6 | 1rem | 500 | 1.2 |
| corpo (body) | 1rem | 400 | 1.5 |
| small | 0.875em | - | - |
| nav-link | small + fw-bolder | 700 | - |

### Display headings (responsive com clamp via calc)

Os display headings usam `calc()` com viewport width para escalonamento fluido:

```css
h1 { font-size: calc(1.375rem + 1.5vw); }  /* min ~1.38rem, max 2.5rem */
h2 { font-size: calc(1.325rem + 0.9vw); }   /* min ~1.33rem, max 2rem */
h3 { font-size: calc(1.3rem + 0.6vw); }     /* min ~1.3rem, max 1.75rem */
h4 { font-size: calc(1.275rem + 0.3vw); }   /* min ~1.28rem, max 1.5rem */
```

### Classes de texto

| Classe | Uso |
|---|---|
| `.text-primary` | Cor primaria (#1e30f3) |
| `.text-secondary` | Cor secundaria (#e21e80) |
| `.text-gradient` | Texto com degradê azul-rosa |
| `.text-muted` | Texto secundario discreto (#6c757d) |
| `.text-uppercase` | Texto em maiusculas |
| `.fw-bolder` | Peso extra forte (700+) |
| `.fw-light` | Peso leve (300) |
| `.fw-bold` | Peso forte (700) |
| `.fs-2, .fs-6` | Variacoes de tamanho de fonte |

## 4. Componentes

### 4.1 Navbar

```html
<nav class="navbar navbar-expand-lg navbar-light bg-white py-3">
  <div class="container px-5">
    <a class="navbar-brand" href="index.html">
      <span class="fw-bolder text-primary">Nome do Projeto</span>
    </a>
    <button class="navbar-toggler" ...>
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse">
      <ul class="navbar-nav ms-auto mb-2 mb-lg-0 small fw-bolder">
        <li class="nav-item">
          <a class="nav-link" href="page.html">Link</a>
        </li>
      </ul>
    </div>
  </div>
</nav>
```

**Caracteristicas**: Fundo branco, colapsa em mobile, links alinhados a direita com peso `fw-bolder`, brand em cor primaria.

### 4.2 Header / Hero Section

```html
<header class="py-5">
  <div class="container px-5 pb-5">
    <div class="row gx-5 align-items-center">
      <div class="col-xxl-5">
        <div class="badge bg-gradient-primary-to-secondary text-white mb-4">
          <div class="text-uppercase">Categorias</div>
        </div>
        <div class="fs-3 fw-light text-muted">Tagline</div>
        <h1 class="display-3 fw-bolder mb-5">
          <span class="text-gradient d-inline">Titulo Principal</span>
        </h1>
        <div class="d-grid gap-3 d-sm-flex">
          <a class="btn btn-primary btn-lg ...">CTA Primario</a>
          <a class="btn btn-outline-dark btn-lg ...">CTA Secundario</a>
        </div>
      </div>
      <div class="col-xxl-7">
        <div class="profile bg-gradient-primary-to-secondary">
          <img class="profile-img" src="assets/photo.png" alt="..." />
          <div class="dots-1"><svg>...</svg></div>
          <div class="dots-2"><svg>...</svg></div>
          <div class="dots-3"><svg>...</svg></div>
          <div class="dots-4"><svg>...</svg></div>
        </div>
      </div>
    </div>
  </div>
</header>
```

**Caracteristicas**: Layout 2 colunas (texto + imagem), badge gradiente, titulo com gradient text, botões de acao.

### 4.3 Profile Card (foto com borda gradiente e dots)

```html
<div class="profile bg-gradient-primary-to-secondary">
  <img class="profile-img" src="photo.png" alt="..." />
  <div class="dots-1"><svg>...</svg></div>
  <div class="dots-2"><svg>...</svg></div>
  <div class="dots-3"><svg>...</svg></div>
  <div class="dots-4"><svg>...</svg></div>
</div>
```

**CSS chave**:

```css
.profile {
  position: relative;
  border-radius: 50%;
  background: linear-gradient(135deg, #1e30f3 0%, #e21e80 100%);
}
.profile .profile-img {
  height: 80vw;
  max-height: 45rem;
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  border-radius: 50%;
}
```

Tamanho responsivo via vw:

| Breakpoint | .profile | .profile-img |
|---|---|---|
| < 576px | 75vw | 80vw |
| >= 576px | 60vw | 65vw |
| >= 768px | 50vw | 55vw |
| >= 992px | 40vw | 45vw |
| >= 1200px | 35vw | 40vw |

### 4.4 Cards

**Card simples com sombra**:

```html
<div class="card shadow border-0 rounded-4 mb-5">
  <div class="card-body p-5">
    ...conteudo...
  </div>
</div>
```

**Card de educacao (sem imagem lateral)**:

```html
<div class="card overflow-hidden shadow rounded-4 border-0 mb-5">
  <div class="card-body p-0">
    <div class="d-flex align-items-center">
      <div class="p-5">
        <h2 class="fw-bolder">Titulo</h2>
        <p>Descricao</p>
      </div>
    </div>
  </div>
</div>
```

**Caracteristicas**: `border-0`, `rounded-4` (border-radius: 1rem), `shadow` (box-shadow com profundidade), padding generoso (p-5).

### 4.5 Skill Cards

```html
<div class="card shadow border-0 rounded-4 mb-5">
  <div class="card-body p-5">
    <div class="d-flex align-items-center mb-4">
      <div class="feature bg-primary bg-gradient-primary-to-secondary text-white rounded-3 me-3">
        <i class="bi bi-tools"></i>
      </div>
      <h3 class="fw-bolder mb-0">
        <span class="text-gradient d-inline">Secao</span>
      </h3>
    </div>
    <div class="row row-cols-1 row-cols-md-3 mb-4">
      <div class="col mb-4 mb-md-0">
        <div class="d-flex align-items-center bg-light rounded-4 p-3 h-100">
          Habilidade 1
        </div>
      </div>
      <!-- mais cols -->
    </div>
  </div>
</div>
```

### 4.6 Badge

```html
<div class="badge bg-gradient-primary-to-secondary text-white mb-4">
  <div class="text-uppercase">Categorias</div>
</div>
```

**Caracteristicas**: Fundo gradiente, texto maiusculas, padding compacto.

### 4.7 Feature Icon

```html
<div class="feature bg-primary bg-gradient-primary-to-secondary text-white rounded-3 me-3">
  <i class="bi bi-tools"></i>
</div>
```

**CSS**: 3x3rem, inline-flex, centro alinhado, icone branco, fundo gradiente.

### 4.8 Botões

| Classe | Apariencia | Uso |
|---|---|---|
| `.btn-primary` | Fundo gradiente azul-rosa, texto branco | CTA principal |
| `.btn-outline-dark` | Borda escura, fundo transparente | CTA secundario |
| `.btn-outline-light` | Borda clara, fundo transparente | Acoes sutis |

**Tamanhos padrao**: `btn-lg` para hero, tamanho normal para cards e secoes.

### 4.9 Secao com fundo claro

```html
<section class="bg-light py-5">
  <div class="container px-5">
    <div class="row gx-5 justify-content-center">
      <div class="col-xxl-8">
        <div class="text-center my-5">
          <h2 class="display-5 fw-bolder">
            <span class="text-gradient d-inline">Titulo</span>
          </h2>
          <p class="lead fw-light">...</p>
          <p class="text-muted">...</p>
        </div>
      </div>
    </div>
  </div>
</section>
```

### 4.10 Footer

```html
<footer class="bg-white py-4 mt-auto">
  <div class="container px-5">
    <div class="row align-items-center justify-content-between flex-column flex-sm-row">
      <div class="col-auto">
        <div class="small m-0">Copyright &copy; Nome Ano</div>
      </div>
    </div>
  </div>
</footer>
```

### 4.11 Contact Cards

```html
<div class="contact-grid">
  <a class="contact-card contact-linkedin" href="https://linkedin.com/...">
    <span class="contact-icon"><i class="bi bi-linkedin"></i></span>
    <span class="contact-copy">
      <span class="contact-title">LinkedIn</span>
      <span class="contact-subtitle">Perfil profissional</span>
    </span>
    <span class="contact-arrow"><i class="bi bi-arrow-up-right"></i></span>
  </a>
</div>
```

**Estrutura**: Grid de cards com icone, titulo, subtítulo e seta. Container com `pacman-panel` e `shadow-sm`.

### 4.12 Pacman Panel

Container reutilizavel para secoes especiais:

```html
<div class="bg-light rounded-4 py-5 px-4 px-md-5 shadow-sm pacman-panel">
  ...
</div>
```

### 4.13 Call-to-Action Section

```html
<section class="py-5">
  <div class="container px-5 my-5">
    <div class="text-center pacman-panel projects-cta">
      <h2 class="display-4 fw-bolder mb-4">Vamos construir algo juntos.</h2>
      <a class="btn btn-outline-dark btn-lg ..." href="contact.html">Contato</a>
    </div>
  </div>
</section>
```

## 5. Layout e Grid

### Breakpoints Bootstrap

| Breakpoint | Largura |
|---|---|
| sm | 576px |
| md | 768px |
| lg | 992px |
| xl | 1200px |
| xxl | 1400px |

### Container

**Padrao**: `.container.px-5` - container centralizado com padding horizontal de 5 rem (15px Bootstrap).

### Grid de conteudo

**Padrao de largura do conteudo**:

```
col-xxl-8   -> max 8 colunas em telas grandes (index.html sobre)
col-xxl-5   -> 5 colunas para hero texto
col-xxl-7   -> 7 colunas para hero imagem
col-lg-11   -> 11 colunas em lg
col-xl-9    -> 9 colunas em xl
col-xxl-8   -> 8 colunas em xxl
```

### Espacamento

| Classe | Valor | Uso |
|---|---|---|
| `py-5` | padding y: 3rem | Secoes verticais |
| `px-5` | padding x: 3rem | Container horizontal |
| `p-5` | padding: 3rem | Card body |
| `mb-5` | margin bottom: 3rem | Separacao de elementos |
| `mb-4` | margin bottom: 1.5rem | Separacao interna |
| `my-5` | margin y: 3rem | Espacamento vertical |
| `gx-5` | gutter x: 3rem | Espacamento entre colunas |

## 6. Background Animado Pac-Man

O background e implementado via Canvas 2D em `js/scripts.js`.

### Elementos visuais

| Elemento | Descricao |
|---|---|
| Grid de fundo | Linhas onduladas suaves em azul (rgba(75, 140, 255, 0.08)) |
| Circuit nodes | Nos de circuito com pulse animado |
| Terminal blocks | Blocos retangulares com dots e texto "> run skill_" |
| Code symbols | Simbolos de codigo flutuantes: `</>`, `{ }`, `[]`, `()`, `01`, `=>`, `fn`, `SQL` |
| Lanes | Linhas onduladas onde os elementos se movem |
| Pellets | Pontos pequenos (ciano) e grandes (amarelo) movendo-se nas lanes |
| Pac-Man | Personagem amarelo com boca animada, move-se nas lanes |
| Ghosts | 5 fantasmas com cores diferentes, se movem nas lanes |
| Sparks | Particulas que seguem o Pac-Man |
| Score | Pontuacao no canto superior direito |

### Classe do tema

```html
<body class="pacman-tech-theme">
```

### Canvas

```html
<canvas id="pacman-background" aria-hidden="true"></canvas>
```

Posicionado no body com `position: fixed` para cobrir toda a tela.

### Reducao de movimento

Respeita `prefers-reduced-motion: reduce` - substitui animacao por render estatico.

## 7. Responsividade

### Padroes de layout responsivo

**Hero (index.html)**:

| Breakpoint | Layout |
|---|---|
| < 768px | Colunas empilhadas verticalmente |
| >= 768px | 2 colunas (texto esquerda, imagem direita) |
| >= 1200px | Espacamento expandido com `col-xxl-*` |

**Cards de experiencia/formacao**:

| Breakpoint | Layout |
|---|---|
| < 768px | 1 coluna |
| >= 768px | Info esquerda, descricao direita |

**Skill cards**:

| Breakpoint | Layout |
|---|---|
| < 768px | 1 coluna |
| >= 768px | 3 colunas |

### Media queries customizadas

- `.profile` e `.dots-*` tem regras especificas para cada breakpoint (576px, 768px, 992px, 1200px)
- `.display-*` headings usam `calc()` com `vw` para scaling fluido
- Breakpoints max-width para correcoes mobile (575.98px, 767.98px, 991.98px, 1199.98px, 1399.98px)

## 8. HTML Boilerplate por Pagina

### Estrutura base (repetida em todas as paginas)

```html
<!DOCTYPE html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
    <meta name="description" content="..." />
    <title>...</title>
    <link rel="icon" type="image/x-icon" href="assets/favicon.ico" />
    <!-- Google Font -->
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@100;200;300;400;500;600;700;800;900&display=swap" rel="stylesheet" />
    <!-- Bootstrap Icons -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.1/font/bootstrap-icons.css" rel="stylesheet" />
    <!-- CSS -->
    <link href="css/styles.css" rel="stylesheet" />
    <link href="responsive-fixes.css" rel="stylesheet" />
  </head>
  <body class="d-flex flex-column h-100 pacman-tech-theme">
    <canvas id="pacman-background" aria-hidden="true"></canvas>
    <main class="flex-shrink-0">
      <!-- Navbar (padrao) -->
      <!-- Conteudo da pagina -->
    </main>
    <!-- Footer (padrao) -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="js/i18n.js"></script>
    <script src="js/scripts.js"></script>
    <script src="js/miriam-widget.js"></script>
  </body>
</html>
```

### Meta tags Open Graph e Twitter

Cada pagina tem suas proprias meta tags OG e Twitter com titulo, descricao, imagem e URL unicos.

```html
<meta property="og:type" content="website" />
<meta property="og:title" content="Nome | Pagina" />
<meta property="og:description" content="..." />
<meta property="og:image" content="https://domain.com/assets/profile.png" />
<meta property="og:url" content="https://domain.com/page.html" />
<meta property="og:site_name" content="Nome do Projeto" />
<meta property="og:locale" content="pt_BR" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="..." />
<meta name="twitter:description" content="..." />
<meta name="twitter:image" content="https://domain.com/assets/profile.png" />
```

## 9. Border Radius

| Classe | Valor |
|---|---|
| `rounded-3` | 0.5rem |
| `rounded-4` | 1rem |
| `rounded-5` | 2rem |
| `rounded-pill` | 50rem |

## 10. Sombras

| Classe | Valor |
|---|---|
| `shadow-sm` | 0 0.125rem 0.25rem rgba(0,0,0,0.075) |
| `shadow` | 0 0.5rem 1rem rgba(0,0,0,0.15) |
| `shadow-lg` | 0 1rem 3rem rgba(0,0,0,0.175) |

## 11. Como Reutilizar em Outro Projeto

### Passo a passo

1. **Copiar arquivos base**: `css/styles.css`, `js/scripts.js`, `responsive-fixes.css`, assets
2. **Criar paginas HTML**: Copiar o boilerplate e adaptar conteudo
3. **Personalizar cores**: Alterar `--bs-primary` e `--bs-secondary` nos `:root` do CSS
4. **Personalizar fontes**: Trocar o Google Fonts link
5. **Ajustar navbar**: Modificar links e brand name
6. **Atualizar footer**: Nome e ano do copyright
7. **Adaptar componentes**: Usar as classes de componenteadas acima como templates
8. **Ajustar SEO**: Meta tags OG/Twitter por pagina

### Pontos de personalizacao rapida

| O que mudar | Onde |
|---|---|
| Cores primarias/secundarias | `:root` em `styles.css`, linhas 37-38 |
| Gradientes | Classes `.bg-gradient-primary-to-secondary` e `.text-gradient` em `styles.css` |
| Fonte | Link do Google Fonts no `<head>` de cada pagina |
| Nome da marca | `.navbar-brand` e `<title>` |
| Links de navegacao | `.navbar-nav` em cada pagina |
| Foto de perfil | Imagem e path em `.profile` |
| Canvas animado | `js/scripts.js` - Pac-Man theme |
| Textos e conteudo | HTML de cada pagina |

### Trocar o tema do background

O canvas em `scripts.js` desenha o tema Pac-Man. Para trocar:

- Modificar as funcoes de desenho: `drawGrid`, `drawProgrammingLayer`, `drawLanes`, `drawPellets`, `drawPacman`, `drawGhost`
- Alterar paleta de cores nos arrays de `ghostPalette`
- Remover elementos nao desejados (ghosts, pellets, code symbols)
- Ou substituir por um efeito completamente novo mantendo a estrutura do canvas

### Remover o Pac-Man theme

Basta remover do `<body>`:
- A classe `pacman-tech-theme`
- A tag `<canvas id="pacman-background">`
- A referencia `<script src="js/scripts.js">`
