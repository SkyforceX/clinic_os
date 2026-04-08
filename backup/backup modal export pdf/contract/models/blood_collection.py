from django.db import models


class BloodCollectionSchedule(models.Model):
    """
    Lịch lấy máu tại doanh nghiệp — một hợp đồng có thể có nhiều buổi lấy máu.

    Thay thế ``booking.BloodCollectionInfo``.
    Được tách ra khỏi app booking vì đây là thông tin thuộc về hợp đồng
    doanh nghiệp, không liên quan đến luồng đặt lịch của bệnh nhân lẻ.
    """

    contract = models.ForeignKey(
        "contract.Contract",
        on_delete=models.CASCADE,
        related_name="blood_collection_schedules",
    )
    collection_date = models.DateField(verbose_name="Ngày lấy máu")
    location        = models.CharField(max_length=255, verbose_name="Địa điểm lấy máu")
    people_count    = models.PositiveIntegerField(verbose_name="Số người được lấy máu")
    staff_count     = models.PositiveIntegerField(verbose_name="Số nhân viên phòng khám")
    note            = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "contract_blood_collection_schedule"
        ordering = ["collection_date"]
        verbose_name = "Lịch lấy máu"
        verbose_name_plural = "Lịch lấy máu"

    def __str__(self):
        return (
            f"{self.contract.contract_number} "
            f"- {self.collection_date} @ {self.location}"
        )
