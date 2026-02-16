# Layout Primitives Reference

## Stack (Vertical Spacing)

```html
<div class="stack">                  <!-- Default: var(--line) -->
<div class="stack stack-compact">    <!-- var(--line-025) -->
<div class="stack stack-half">       <!-- var(--line-05) -->
<div class="stack stack-comfortable"><!-- var(--line-2) -->
<div class="stack stack-spacious">   <!-- var(--line-4) -->
```

## Grid (Auto-Responsive)

```html
<div class="grid">                   <!-- Auto-fit -->
<div class="grid grid-narrow">       <!-- Narrower min column width -->
<div class="grid grid-columns-2">    <!-- Fixed columns -->
<div class="grid grid-columns-2@md"> <!-- 2 cols at 40rem+ container -->
<div class="grid grid-columns-3@lg"> <!-- 3 cols at 60rem+ container -->
<div class="grid-column-span-2">     <!-- Span columns -->
<div class="grid-column-span-2@md">  <!-- Responsive span -->
```

## Cluster (Horizontal Grouping)

```html
<nav class="cluster">
<div class="cluster cluster-compact">  <!-- var(--line-05) gap -->
<div class="cluster cluster-center">   <!-- justify-content: center -->
<div class="cluster cluster-end">      <!-- justify-content: flex-end -->
<div class="cluster cluster-between">  <!-- justify-content: space-between -->
<div class="cluster cluster-nowrap">   <!-- flex-wrap: nowrap (for headers) -->
```

## Sidebar

```html
<div class="sidebar">
<div class="sidebar sidebar-snug">     <!-- var(--line-1) gap -->
<div class="sidebar sidebar-loose">    <!-- var(--line-2) gap -->
<div class="sidebar sidebar-reverse">  <!-- Sidebar on right -->
```

## Center (Max-Width Container)

```html
<div class="center">
<div class="center center-narrow">
<div class="center center-wide">
```

## Section (Vertical Padding)

```html
<section class="section">
<section class="section section-spaced">       <!-- Top + bottom padding -->
<section class="section section-snug">         <!-- Smaller top + bottom -->
<section class="section section-tight">        <!-- No vertical padding -->
<section class="section section-top-tight">    <!-- No top padding -->
<section class="section section-bottom-tight"> <!-- No bottom padding -->
<section class="section section-wide">         <!-- Narrower horizontal padding -->
<section class="section section-full-bleed">   <!-- No padding at all -->
```

## Cover (Full-Height Centering)

```html
<header class="cover">  <!-- min-height: 100vh, flexbox centering -->
```

## Box (Padding Wrapper)

```html
<div class="box">         <!-- var(--line-1) padding -->
<div class="box box-tight"> <!-- var(--line-05) padding -->
<div class="box box-loose"> <!-- var(--line-2) padding -->
```

## Reel (Horizontal Scrolling)

```html
<div class="reel">                   <!-- Default horizontal scroll -->
<div class="reel reel-narrow">       <!-- 8 lines item width -->
<div class="reel reel-medium">       <!-- 12 lines item width -->
<div class="reel reel-wide">         <!-- 16 lines item width -->
<div class="reel reel-compact">      <!-- var(--line-05) gap -->
<div class="reel reel-spacious">     <!-- var(--line-2) gap -->
<div class="reel reel-no-scrollbar"> <!-- Hidden scrollbar -->
<div class="reel reel-padded">       <!-- Bottom padding for overflow -->
```

## Imposter (Overlay Positioning)

```html
<div class="imposter">              <!-- Absolutely centered in parent -->
<div class="imposter-fixed">        <!-- Fixed to viewport -->
<dialog class="imposter-dialog">    <!-- Optimized for <dialog> -->
<dialog class="imposter-dialog imposter-contain"> <!-- Prevents overflow -->
```
