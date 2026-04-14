from django.db import models
from django.conf import settings


class Procedure(models.Model):
    CATEGORY_CHOICES = [
        ('sale', 'Kinh doanh / Bán hàng'),
        ('marketing', 'Marketing'),
        ('clinical', 'Khám chữa bệnh'),
        ('operations', 'Vận hành nội bộ'),
        ('customer_care', 'Chăm sóc khách hàng'),
        ('hr', 'Nhân sự'),
        ('accounting', 'Kế toán'),
        ('quality', 'Chất lượng'),
        ('it', 'Công nghệ thông tin'),
        ('other', 'Khác'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Bản nháp'),
        ('published', 'Đã ban hành'),
        ('archived', 'Lưu trữ'),
    ]

    title = models.CharField('Tên quy trình', max_length=255)
    code = models.CharField('Mã quy trình', max_length=50, unique=True, blank=True)
    category = models.CharField('Loại', max_length=50, choices=CATEGORY_CHOICES, default='other')
    description = models.TextField('Mô tả tổng quan', blank=True)
    status = models.CharField('Trạng thái', max_length=20, choices=STATUS_CHOICES, default='draft')
    version = models.CharField('Phiên bản', max_length=20, default='1.0')
    effective_date = models.DateField('Ngày hiệu lực', null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_procedures',
        verbose_name='Người tạo',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'procedures_procedure'
        ordering = ['-created_at']
        verbose_name = 'Quy trình'
        verbose_name_plural = 'Danh sách quy trình'

    def __str__(self):
        return f'[{self.code}] {self.title}' if self.code else self.title

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._generate_code()
        super().save(*args, **kwargs)

    def _generate_code(self):
        prefix_map = {
            'sale': 'QT-KD',
            'marketing': 'QT-MKT',
            'clinical': 'QT-KCB',
            'operations': 'QT-VH',
            'customer_care': 'QT-CSKH',
            'hr': 'QT-NS',
            'accounting': 'QT-KT',
            'quality': 'QT-CL',
            'it': 'QT-IT',
            'other': 'QT',
        }
        prefix = prefix_map.get(self.category, 'QT')
        count = Procedure.objects.filter(category=self.category).count() + 1
        return f'{prefix}-{count:03d}'

    @property
    def status_badge(self):
        return {'draft': 'secondary', 'published': 'success', 'archived': 'dark'}.get(self.status, 'secondary')

    @property
    def step_count(self):
        return self.steps.count()


class ProcedureStep(models.Model):
    COLOR_CHOICES = [
        ('#0d6efd', 'Xanh dương'),
        ('#198754', 'Xanh lá'),
        ('#dc3545', 'Đỏ'),
        ('#fd7e14', 'Cam'),
        ('#6f42c1', 'Tím'),
        ('#0dcaf0', 'Xanh lơ'),
        ('#20c997', 'Ngọc lam'),
        ('#6c757d', 'Xám'),
        ('#212529', 'Đen'),
    ]

    procedure = models.ForeignKey(
        Procedure, on_delete=models.CASCADE,
        related_name='steps', verbose_name='Quy trình',
    )
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='children', verbose_name='Bước cha',
    )
    title = models.CharField('Tên bước', max_length=255)
    description = models.TextField('Mô tả chi tiết', blank=True)
    responsible = models.CharField('Người / Bộ phận thực hiện', max_length=255, blank=True)
    duration = models.CharField('Thời gian thực hiện', max_length=100, blank=True)
    order = models.PositiveIntegerField('Thứ tự', default=0)
    color = models.CharField('Màu sắc', max_length=7, default='#0d6efd')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'procedures_step'
        ordering = ['order', 'pk']
        verbose_name = 'Bước quy trình'

    def __str__(self):
        return self.title

    def to_dict(self):
        return {
            'id': self.pk,
            'parent_id': self.parent_id,
            'title': self.title,
            'description': self.description,
            'responsible': self.responsible,
            'duration': self.duration,
            'order': self.order,
            'color': self.color,
            'attachment_count': self.attachments.count(),
        }


class ProcedureAttachment(models.Model):
    TYPE_CHOICES = [
        ('image', 'Hình ảnh'),
        ('pdf', 'PDF'),
        ('other', 'Khác'),
    ]

    procedure = models.ForeignKey(
        Procedure, on_delete=models.CASCADE,
        null=True, blank=True, related_name='attachments',
    )
    step = models.ForeignKey(
        ProcedureStep, on_delete=models.CASCADE,
        null=True, blank=True, related_name='attachments',
    )
    name = models.CharField('Tên tài liệu', max_length=255)
    file = models.FileField('Tệp', upload_to='procedures/attachments/')
    file_type = models.CharField('Loại tệp', max_length=10, choices=TYPE_CHOICES, default='other')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='procedure_attachments',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'procedures_attachment'
        ordering = ['uploaded_at']

    def __str__(self):
        return self.name

    def to_dict(self):
        return {
            'id': self.pk,
            'name': self.name,
            'file_url': self.file.url,
            'file_type': self.file_type,
            'step_id': self.step_id,
            'uploaded_at': self.uploaded_at.strftime('%d/%m/%Y'),
        }
