import { Component, EventEmitter, Input, Output, inject } from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { DocumentBundle } from 'src/app/data/document-bundle'

@Component({
  selector: 'pngx-document-bundle-edit-dialog',
  templateUrl: './document-bundle-edit-dialog.component.html',
  imports: [FormsModule, ReactiveFormsModule],
})
export class DocumentBundleEditDialogComponent {
  private readonly activeModal = inject(NgbActiveModal)

  @Input()
  bundle: DocumentBundle

  @Output()
  saved = new EventEmitter<{ bundle_id: string }>()

  closeEnabled = false

  bundleForm = new FormGroup({
    bundle_id: new FormControl(''),
  })

  ngOnInit(): void {
    this.bundleForm.patchValue({
      bundle_id: this.bundle?.bundle_id ?? '',
    })
    setTimeout(() => {
      this.closeEnabled = true
    })
  }

  save(): void {
    this.saved.emit({
      bundle_id: this.bundleForm.value.bundle_id ?? '',
    })
  }

  close(): void {
    this.activeModal.close()
  }
}
