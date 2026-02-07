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
    sku = models.CharField(max_length=50, unique=True, blank=True, null=True)  # Optional SKU
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
            # Generate slug from name and a unique identifier
            base_slug = slugify(self.name)
            if self.sku:
                self.slug = slugify(f"{self.name}-{self.sku}")
            else:
                # Use part of UUID for uniqueness if no SKU
                unique_suffix = str(self.id)[:8] if self.id else str(uuid.uuid4())[:8]
                self.slug = f"{base_slug}-{unique_suffix}"
        
        # Generate barcode if not exists (auto-generate unique barcode with prefix)
        if not self.barcode:
            from apps.products.models import StoreSettings
            prefix = StoreSettings.get_barcode_prefix()
            timestamp = str(int(__import__('time').time()))[-10:]
            random_suffix = str(__import__('random').randint(10, 99))
            self.barcode = f"{prefix}-{timestamp}{random_suffix}"
        
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
        variants = self.variants.filter(is_active=True)
        if variants.exists():
            return any(v.stock_quantity <= v.low_stock_threshold for v in variants)
        return self.stock_quantity <= self.low_stock_threshold

    @property
    def is_out_of_stock(self):
        variants = self.variants.filter(is_active=True)
        if variants.exists():
            return all(v.stock_quantity == 0 for v in variants)
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
    low_stock_threshold = models.PositiveIntegerField(default=10)
    
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


class StoreSettings(models.Model):
    """Singleton model for store settings including barcode prefix."""
    
    barcode_prefix = models.CharField(
        max_length=10, 
        default='ZZ',
        help_text='Prefix for auto-generated barcodes (e.g., 123 for 123-XXXXXXXXXX)'
    )
    
    # Popular searches (comma-separated terms shown in search modal)
    popular_searches = models.TextField(
        blank=True,
        default='Borkha,Hijab,Abaya,Niqab',
        help_text='Comma-separated popular search terms shown in search modal'
    )
    
    # Contact information
    contact_address = models.TextField(
        blank=True,
        default='123 Fashion Street, Gulshan, Dhaka 1212, Bangladesh',
        help_text='Full store address'
    )
    contact_phone_1 = models.CharField(max_length=20, blank=True, default='+880 1234-567890')
    contact_phone_2 = models.CharField(max_length=20, blank=True, default='+880 1234-567891')
    contact_email_1 = models.EmailField(blank=True, default='contact@zzuhana.com')
    contact_email_2 = models.EmailField(blank=True, default='support@zzuhana.com')
    business_hours = models.TextField(
        blank=True,
        default='Sat - Thu: 10:00 AM - 8:00 PM\nFriday: Closed',
        help_text='Business hours (one line per entry)'
    )
    
    # Map embed
    map_embed_url = models.URLField(
        max_length=1000,
        blank=True,
        default='https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d14602.254272231177!2d90.41259!3d23.7925!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x3755c7a0f70deb73%3A0x30c36498f90fe23!2sGulshan%2C%20Dhaka!5e0!3m2!1sen!2sbd!4v1640000000000!5m2!1sen!2sbd',
        help_text='Google Maps embed URL for the contact page'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Store Settings'
        verbose_name_plural = 'Store Settings'

    def __str__(self):
        return f"Store Settings (Barcode Prefix: {self.barcode_prefix})"

    def save(self, *args, **kwargs):
        # Ensure only one instance exists (singleton pattern)
        if not self.pk and StoreSettings.objects.exists():
            existing = StoreSettings.objects.first()
            self.pk = existing.pk
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance."""
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings

    @classmethod
    def get_barcode_prefix(cls):
        """Get the current barcode prefix."""
        try:
            settings = cls.objects.first()
            return settings.barcode_prefix if settings else 'ZZ'
        except Exception:
            return 'ZZ'
