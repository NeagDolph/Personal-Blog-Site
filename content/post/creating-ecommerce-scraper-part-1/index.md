---
title: "Scraping Ecommerce Sites Using LLMs - Part 1"
date: 2025-06-26T10:00:00Z
description: "Part 1 of a series where I learn to extract product data from ecommerce websites using LLMs"
tags: ["ai", "algorithms", "python", "scraping", "ecommerce"]
categories: ["Artificial Intelligence"]
author: "Neil Agrawal"
showToc: false
seriesOpened: false
series: ["Scraping Ecommerce Sites Using LLMs"]
series_order: 1
---

{{< lead >}}
What if you could extract product data from **any ecommerce website** without writing a single line of custom scraping code?

I spent the last month building exactly that - a universal ecommerce scraper powered by LLMs. No more brittle XPath selectors that break when a site updates. No more maintaining dozens of site-specific parsers. Just point it at any online store and watch it extract products like magic.

Here's the catch: doing this naively with LLMs would cost a fortune. My first attempt burned through millions of tokens trying to scrape a single website. But after some optimization, I've gotten that down to only 5-10k tokens per site while actually *improving* accuracy.

This is part 1 of a series where I'll show you how to build a scraper that can handle everything from tiny Shopify stores to e-commerce giants like QVC. Along the way, we'll dive into some fascinating problems, like filtering HTML using NLP Models, or generating reusable extraction schemas that work across thousands of pages.

{{< /lead >}}

## The Plan

Since there's so much variability in how HTML is structured for different websites, we need an approach that's adaptable and can understand the nuance of each website's layout. LLMs like ChatGPT are a great tool to throw at this kind of problem since they can understand the structure of each page well enough without having to write custom scraping tools for each e-commerce store.

There are **two main aspects** to product extraction. 

1. **Finding Category Links:** We need to find the URL's for all PLPs (product listing pages) where products are listed. 

2. **Extracting Products:** we need to extract the title, price, description, image URL, etc for each product and from each PLP.

## Finding Category Links

The first step to scraping products from e-commerce websites is actually finding the pages that products are listed on. This is harder than it sounds because not only do we have to recursively scrape each link on the site but we also have to determine if a link has products on it or not.

### Approach 1: Pass it all to an LLM
When you have a hammer, everything looks like a nail. We could simply throw the HTML from each and every link to an LLM and ask it to extract the products. Most of the time this will work but it's incredibly expensive and takes a long time to run.

```python
visited_urls = set()
all_products = []

def crawl_and_extract(url):
    if url in visited_urls:
        return
    visited_urls.add(url)
    
    # Scrape the page
    html_content = scrape_page(url)
    
    # Pass entire HTML to LLM
    prompt = f"""
    Extract all products from this HTML page. For each product, return in JSON format:
    [
        {
        "title": "PRODUCT TITLE",
        "price": "PRODUCT PRICE",
        "description": "PRODUCT DESCRIPTION",
        "image_url": "IMAGE URL",
        "product_url": "PRODUCT URL"
        }
    ]
    
    If no products found, return empty list.
    
    HTML: {html_content}
    """
    
    response = llm_call(prompt)

    products = parse_llm_response(response)
    all_products.extend(products)
    
    # Find all links on the page
    links = extract_links(html_content)
    
    # Recursively crawl each link
    for link in links:
        crawl_and_extract(link)

crawl_and_extract(base_url)
return all_products
```

This script visits a webpage, extracts the products from it, and recursively visits all the linked pages and does the same. 

### Approach 2: Pass only the links to an LLM
This approach worked a lot better for me. I simply aggregate all the scraped URLs and then pass them to an LLM, prompting it to return only the links it thinks are "PLP pages".

```python
    products = set()
    # Step 1: Crawl all URLs on the site
    all_urls = crawl_all_urls(base_url)
    
    # Step 2: Use LLM to filter which URLs are PLPs
    prompt = f"""
    Given these URLs from an ecommerce website, identify which ones are likely 
    Product Listing Pages (PLPs) - pages that show multiple products.
    
    Return only the URLs that are PLPs.
    
    URLs: {all_urls}
    """
    
    plp_urls = llm_call(prompt)

    for url in plp_urls:
        products.extend(extract_products(url))

```

Sometimes the LLM includes non-plp pages and omits pages with products, but this works most of the time and only requires one LLM call per site we're trying to scrape category links from.

## Extracting Products

Now we have a set of PLP URLs that likely contain products. The next challenge is extracting structured product data from each page. This is where things get interesting, and potentially expensive if we're not careful.

### Approach 1: Pass it all to an LLM (again)

My first instinct again was to just pass the entire HTML of each product page to an LLM and ask it to extract products.

```python
def extract_products_naive(url):
    html = scrape_page(url)
    
    prompt = f"""
    Extract all products from this HTML. Return JSON with:
    - name
    - price  
    - image_url
    - product_url
    
    HTML: {html}
    """
    
    return llm_call(prompt)
```

This actually works! The LLM can look at the HTML and figure out what's a product, what's the price, etc. But there are some serious problems:

1. **Token Limits**: E-commerce pages are HUGE. A single PLP can easily exceed 100k+ tokens when you include all the HTML, script tags, style tags, etc.
2. **Cost**: At current API pricing, extracting products from a single website could cost hundreds of dollars.
3. **Speed**: Processing that much HTML through an LLM is really slow.
4. **Reliability**: The LLM might miss products or hallucinate data that isn't there.

> In general, we want to avoid just throwing massive amounts of data into LLMs. It's expensive and often produces unreliable results.

### HTML Cleaning

My next iteration involved cleaning the HTML before sending it to the LLM. Strip out all the scripts, styles, tracking pixels, and other junk:

```python
def clean_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove script, style and nav elements
    for tag in soup(["script", "style", "meta", "link", "noscript", "nav", "header", "footer", "aside"]):
        tag.decompose()
    
    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    
    # Only keep necessary attributes
    for tag in soup.find_all(True):
        tag.attrs = {key: val for key, val in tag.attrs.items() 
                    if key in ['class', 'id', 'href', 'src']}
    
    return str(soup)
```

This helped reduce the token count significantly, but we were still looking at 20-50k tokens per page. Better, but not great.

### Better HTML Cleaning: The Content Filter

The problem with our current HTML cleaning is that it's too basic. We're removing obviously useless stuff, but we're still keeping everything else - promos, sidebars, "recommended products" sections, newsletter signups, and a million other things that aren't the actual products we want.

What we really need is a way to identify and extract just the product-containing sections of the page. Enter the Content Filter - my attempt at building an intelligent HTML filter that can identify "product-like" content across any e-commerce site.

The core idea is simple: **score every HTML element based on how likely it is to contain product information, then keep only the highest-scoring elements**.

Here's how the scoring works:

```python
def _score_element(self, tag: Tag, text: str) -> float:
    """Scores an element based on NLP analysis and keyword-matching"""
    doc = self.nlp(text[:self.nlp.max_length])
    score = 0.0

    # Score based on named entities found by spaCy
    entity_scores = {"MONEY": 2.5, "PRODUCT": 2.0, "ORG": 0.5}
    for ent in doc.ents:
        score += entity_scores.get(ent.label_, 0)

    # Score based on product-related keywords
    product_keywords = ["sale", "discount", "offer", "review", "rating", "brand", "sku", "model", "cart", "product"]
    score += sum(0.25 for keyword in product_keywords if keyword in text.lower())

    # Structural and density bonuses
    if tag.find('img'): score += 0.1 # HTML with images is likelier to be a product
    if tag.find(['button', 'a'], text=re.compile(r"add|buy|cart", re.I)): score += 1.0 # Add to cart buttons indicative of products
    score += (len(text) / (len(str(tag)) + 1e-6))  # Text-to-HTML ratio

    return score
```

Let's break down what's happening:

1. **NLP Entity Recognition**: We use spaCy to identify named entities. Named Entity Recognition (NER) works by using machine learning models trained on labeled text data to classify spans of text into predefined categories. The model analyzes patterns like capitalization, surrounding words, character patterns, and positional context to determine if something is a MONEY entity ("$29.99"), an ORG entity ("Nike"), or other types. When spaCy processes our HTML text, it outputs these classified entities, which we then score - money entities get the highest score because products usually have prices.

2. **Keyword Matching**: We look for product-related keywords. Words like "sale", "discount", "rating" are good indicators that we're looking at product-like content.

3. **Structural Analysis**: 
   - Elements with images get bonus points (products usually have images)
   - Elements with "Add to Cart" or "Buy Now" buttons score even higher
   - We calculate the text-to-HTML ratio - product cards tend to have a good balance of content vs markup

But scoring is only half the battle. We also need to filter out the junk:

```python
# Pre-filtering navigation and junk sections
NAV_PATTERNS = [
    r"(?:nav|navigation|menu|header|footer|sidebar|breadcrumb)",
    r"(?:filter|sort|pagination|paging)", 
    r"(?:newsletter|signup|login)",
    r"(?:social|share|follow)", 
    r"(?:banner|ad|promo|marketing)",
]

def _is_navigation_element(self, tag: Tag, text: str) -> bool:
    """Checks if an element is likely part of navigation, a header, or a footer."""
    if tag.name in ["nav", "header", "footer", "aside"]:
        return True
    attr_text = " ".join([tag.get("id", ""), " ".join(tag.get("class", [])), tag.get("role", "")]).lower()
    if self.NEG_CLASS_RX.search(attr_text):
        return True
    return False
```

This pre-filtering step quickly eliminates obvious non-product content based on HTML structure and CSS classes. No point in running computationally expensive NLP on a footer menu.

#### The Tree Problem

When we score individual elements, we might end up with a bunch of highly-scored elements that are nested inside each other. For example:

```html
<div class="product-grid">  <!-- High score -->
    <div class="product-card">  <!-- Also high score -->
        <h3>Product Name</h3>  <!-- Also high score -->
        <span class="price">$29.99</span>  <!-- Very High score -->
    </div>
</div>
```

We don't want to extract the same product four times, so we need to deduplicate our HTML nodes.

1. We identify all candidate product elements less than 800 characters (so we don't end up deduplicating all the way up the tree)
2. For each candidate, check if it's nested inside another candidate
3. If a node is nested inside another, we remove it from our final list
4. We transfer the highest score to the parent element (if child had higher score)

This ensures we just keep the high level elements that contain product information, and not all their children.

#### The Result

After all this processing, we end up with a clean set of HTML snippets that contains actual product data, with all the useless tags removed. Instead of 100k tokens of messy HTML, we might have 5-10k tokens of highly relevant content. Of course, this system requires some parameter-tuning to get right, but generally performs well on most ecommerce websites.

The content filter reduced our token usage by another 70-80% compared to basic HTML cleaning, while actually *improving* extraction accuracy by focusing the LLM's attention on the right content.

### Approach 2: Schema-Based Extraction

Here's where things get interesting. What if instead of asking the LLM to extract products from HTML every single time, we ask it to learn the **structure** of the website once, and then use that knowledge to extract products programmatically?

1. Show the LLM a sample of the HTML
2. Ask it to generate a "schema" - a recipe for extracting products
3. Use that schema with an HTML parser to extract products from all pages

Here's what a schema might look like:

```json
{
  "name": "Products",
  "baseSelector": "div.product-card",
  "fields": [
    {
      "name": "name",
      "selector": "h3.product-title",
      "type": "text"
    },
    {
      "name": "price",
      "selector": "span.price",
      "type": "text"
    },
    {
      "name": "image_url",
      "selector": "img.product-image",
      "type": "attribute",
      "attribute": "src"
    }
  ]
}
```

And its output might look like this:

```json
[
  {
    "name": "Wireless Bluetooth Headphones",
    "price": "$29.99",
    "image_url": "https://example.com/images/headphones.jpg"
  },
  {
    "name": "Smart Watch Series 5",
    "price": "$199.99",
    "image_url": "https://example.com/images/smartwatch.jpg"
  }
]
```

The amazing part about this approach is that we only need to use the LLM once per website. After that, we can extract thousands of products using simple CSS selectors.

By combining content filtering with schema generation, we can now show the LLM just the relevant parts of the page, making schema generation faster, more accurate, and cheaper.

### Putting It All Together

Here's how the final flow works:

**First time seeing a website**: Generate a schema
   1. Extract product-like sections using NLP
   2. Show samples to LLM
   3. Get back a CSS selector-based schema
   4. Cache schema for future use

**Extracting products**: Use the cached schema
   1. Parse HTML with BeautifulSoup
   2. Apply CSS selectors from schema
   3. Extract and validate product data

We went from using over 100k input tokens per page to less than 10k input tokens for an entire website. And extraction is nearly instantaneous since we're just using CSS selectors.

## Challenges

Here are some challenges/edge-cases I encountered:

- **Sale banners/promotional content** Often score high in content filters because they contain product-like language
- **Category pages without products** Pages that describe categories but don't actually list any products
- **Variant selectors** Products with multiple options affecting price/availability
- **Anti-scraping measures** Captchas, IP blocking, and honeypot links

## Conclusion

- LLMs are great at understanding structure, but expensive for repetitive tasks
- Generating reusable schemas instead of processing every page leads to better results for cheaper
- Use relatively cheap NLP to reduce the problem space before involving expensive generative AI
- Cache aggressively - website structures don't change that often

In subsequent parts I'll go over handling pagination, improved PLP page classification, dealing with anti-scraping measures, and training custom NER models.

---

*Check out the [implementation](https://github.com/NeagDolph/competitive) on GitHub.*






