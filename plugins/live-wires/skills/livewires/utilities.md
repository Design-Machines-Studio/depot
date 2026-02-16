# Utilities Reference

## Typography Utilities

```html
<!-- Sizes -->
<p class="text-xs">  <p class="text-sm">  <p class="text-base">
<p class="text-lg">  <p class="text-xl">  <p class="text-2xl">
<p class="text-3xl"> <p class="text-4xl"> <p class="text-5xl"> <p class="text-6xl">
<p class="text-7xl"> <p class="text-8xl"> <p class="text-9xl">

<!-- Responsive sizes (container queries) -->
<h1 class="text-4xl text-6xl@md text-8xl@lg">  <!-- Scales up at breakpoints -->

<!-- Weights -->
<p class="font-light">  <p class="font-normal">  <p class="font-medium">
<p class="font-semibold">  <p class="font-bold">  <p class="font-black">

<!-- Alignment -->
<p class="text-left">  <p class="text-center">  <p class="text-right">

<!-- Special -->
<p class="lead">       <!-- Larger intro paragraph -->
<p class="measure">    <!-- Optimal reading width (65ch) -->
<span class="dropcap"> <!-- Large initial letter -->
```

## Spacing Utilities

```html
<!-- Margin: mt, mb, my, ml, mr, mx -->
<div class="mt-2">  <!-- margin-block-start: var(--line-2) -->
<div class="mb-3">  <!-- margin-block-end: var(--line-3) -->
<div class="my-4">  <!-- margin-block: var(--line-4) -->

<!-- Padding: pt, pb, py, pl, pr, px, p -->
<div class="py-3">  <!-- padding-block: var(--line-3) -->
<div class="px-2">  <!-- padding-inline: var(--line-2) -->
<div class="p-4">   <!-- padding: var(--line-4) -->
```

**Values:** 0, 025, 05, 075, 1, 15, 2, 3, 4, 5, 6

## Color Schemes

```html
<section class="scheme-subtle">    <!-- Light grey -->
<section class="scheme-dark">      <!-- Dark bg, light text -->
<section class="scheme-grey-100">  <!-- Grey 100 -->
<section class="scheme-grey-200">  <!-- Grey 200 -->

<!-- Background/text colors -->
<div class="bg-white">  <div class="bg-black">  <div class="bg-grey-100">
<p class="text-white">  <p class="text-muted">  <p class="text-grey-500">
```

## Container Query Breakpoints

- `@md` = 40rem container width
- `@lg` = 60rem container width

```html
<!-- Grid -->
<div class="grid-columns-2@md">     <!-- 2 cols at 40rem+ -->
<div class="grid-column-span-2@lg"> <!-- Span 2 at 60rem+ -->

<!-- Typography -->
<h1 class="text-4xl text-6xl@md text-8xl@lg"> <!-- Scales up at breakpoints -->

<!-- Order -->
<div class="order-first@md">        <!-- Order first at 40rem+ -->
```
