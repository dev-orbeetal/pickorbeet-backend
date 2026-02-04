"""
Product models for Zzuhana E-commerce.
"""
from django.db import models
from django.conf import settings
from django.utils.text import slugify
import uuid
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
from django.core.files import File


class Category(models.Model):
    """Category model with image support."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    tagline = models.CharField(max_length=150, blank=True, null=True, help_text='Short tagline for featured display')
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    banner_image = models.ImageField(upload_to='categories/banners/', blank=True, null=True, help_text='Large banner image for homepage featured section')
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text='Display in homepage featured section')
    featured_order = models.PositiveIntegerField(default=0, help_text='Order in featured section')
    display_order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def product_count(self):
        return self.products.filter(is_active=True).count()


class SubCategory(models.Model):
    """SubCategory model with image support."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, blank=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='subcategories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Sub Category'
        verbose_name_plural = 'Sub Categories'
        ordering = ['display_order', 'name']
        unique_together = ['category', 'name']

    def __str__(self):
        return f"{self.category.name} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.category.name}-{self.name}")
        super().save(*args, **kwargs)

    @property
    def product_count(self):
        return self.products.filter(is_active=True).count()


class Product(models.Model):
    """Product model with barcode, stock management."""
    
    SIZE_CHOICES = [
        ('XS', 'Extra Small'),
        ('S', 'Small'),
        ('M', 'Medium'),
        ('L', 'Large'),
        ('XL', 'Extra Large'),
        ('XXL', 'Double XL'),
        ('XXXL', 'Triple XL'),
        ('FREE', 'Free Size'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    sku = models.CharField(max_length=50, unique=True)
    barcode = models.CharField(max_length=50, unique=True, blank=True, null=True)
    barcode_image = models.ImageField(upload_to='barcodes/', blank=True, null=True)
    
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    subcategory = models.ForeignKey(SubCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    
    description = models.TextField(blank=True, null=True)
    short_description = models.CharField(max_length=500, blank=True, null=True)
    
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    size = models.CharField(max_length=10, choices=SIZE_CHOICES, blank=True, null=True)
    color = models.CharField(max_length=50, blank=True, null=True)
    material = models.CharField(max_length=100, blank=True, null=True)
    
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=10)
    
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.name}-{self.sku}")
        
        # Generate barcode if not exists
        if not self.barcode:
            self.barcode = self.sku
        
        # Generate barcode image
        if self.barcode and not self.barcode_image:
            self.generate_barcode_image()
        
        super().save(*args, **kwargs)

    def generate_barcode_image(self):
        """Generate barcode image for the product."""
        try:
            EAN = barcode.get_barcode_class('code128')
            ean = EAN(self.barcode, writer=ImageWriter())
            buffer = BytesIO()
            ean.write(buffer)
            self.barcode_image.save(f'barcode_{self.sku}.png', File(buffer), save=False)
        except Exception:
            pass

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold

    @property
    def is_out_of_stock(self):
        return self.stock_quantity == 0

    @property
    def discount_percentage(self):
        if self.compare_price and self.compare_price > self.price:
            return int(((self.compare_price - self.price) / self.compare_price) * 100)
        return 0

    @property
    def primary_image(self):
        primary = self.images.filter(is_primary=True).first()
        if primary:
            return primary.image.url
        first_image = self.images.first()
        return first_image.image.url if first_image else None


class ProductImage(models.Model):
    """Product images model."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    alt_text = models.CharField(max_length=255, blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Product Image'
        verbose_name_plural = 'Product Images'
        ordering = ['display_order']

    def __str__(self):
        return f"{self.product.name} - Image {self.display_order}"

    def save(self, *args, **kwargs):
        # If this is primary, unset other primary images
        if self.is_primary:
            ProductImage.objects.filter(product=self.product, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)


class ProductVariant(models.Model):
    """Product variants for different sizes/colors."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=50, unique=True)
    barcode = models.CharField(max_length=50, unique=True, blank=True, null=True)
    
    size = models.CharField(max_length=10, choices=Product.SIZE_CHOICES, blank=True, null=True)
    color = models.CharField(max_length=50, blank=True, null=True)
    
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Product Variant'
        verbose_name_plural = 'Product Variants'
        unique_together = ['product', 'size', 'color']

    def __str__(self):
        return f"{self.product.name} - {self.size} - {self.color}"

    @property
    def effective_price(self):
        return self.price if self.price else self.product.price
