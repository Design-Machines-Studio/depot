# Common Patterns Reference

## Article Structure

```html
<article class="prose">
  <header class="section scheme-subtle">
    <h1 class="text-6xl">Title</h1>
    <p class="lead">Subtitle.</p>
    <p>By Author &middot; <time datetime="2024-01-15">January 15, 2024</time></p>
  </header>
  <figure class="section section-tight">
    <img src="hero.jpg" alt="" />
    <figcaption>Caption.</figcaption>
  </figure>
  <div class="section section-top-tight center">
    <p><span class="dropcap">O</span>pening paragraph...</p>
  </div>
  <footer class="section">
    <hr />
    <p><strong>Author</strong> bio.</p>
  </footer>
</article>
```

## Feature Hero

```html
<header class="cover scheme-dark">
  <div class="center text-center">
    <h1 class="text-6xl">Feature Title</h1>
    <p class="lead">Subtitle.</p>
  </div>
</header>
```

## Statistics Grid

```html
<div class="grid grid-columns-4@md text-center">
  <div class="stack stack-compact">
    <p class="text-5xl font-bold">150</p>
    <p>Label</p>
  </div>
</div>
```

## Responsive Picture

```html
<picture>
  <source media="(min-width: 60em)" srcset="4x3.jpg" sizes="75vw" />
  <source media="(min-width: 40em)" srcset="3x2.jpg" sizes="50vw" />
  <source srcset="16x9.jpg" sizes="100vw" />
  <img src="fallback.jpg" alt="" loading="lazy" />
</picture>
```
