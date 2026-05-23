import { Component, EventEmitter, Input, Output, inject } from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { DocumentBundleItem } from 'src/app/data/document-bundle'

@Component({
  selector: 'pngx-document-bundle-item-edit-dialog',
  templateUrl: './document-bundle-item-edit-dialog.component.html',
  imports: [FormsModule, ReactiveFormsModule],
})
export class DocumentBundleItemEditDialogComponent {
  private readonly activeModal = inject(NgbActiveModal)

  @Input()
  item: DocumentBundleItem

  @Output()
  saved = new EventEmitter<{
    bundle_item_name: string
    bundle_item_type: string
  }>()

  closeEnabled = false

  itemForm = new FormGroup({
    bundle_item_name: new FormControl(''),
    bundle_item_type: new FormControl(''),
  })

  ngOnInit(): void {
    this.itemForm.patchValue({
      bundle_item_name: this.item?.bundle_item_name ?? '',
      bundle_item_type: this.item?.bundle_item_type ?? '',
    })
    setTimeout(() => {
      this.closeEnabled = true
    })
  }

  save(): void {
    this.saved.emit({
      bundle_item_name: this.itemForm.value.bundle_item_name ?? '',
      bundle_item_type: this.itemForm.value.bundle_item_type ?? '',
    })
  }

  close(): void {
    this.activeModal.close()
  }
}
