import { HttpTestingController } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { Subscription } from 'rxjs'
import { environment } from 'src/environments/environment'
import { commonAbstractPaperlessServiceTests } from './abstract-paperless-service.spec'
import { DocumentBundleService } from './document-bundle.service'

const endpoint = 'bundles'

commonAbstractPaperlessServiceTests(endpoint, DocumentBundleService)

describe('DocumentBundleService', () => {
  let httpTestingController: HttpTestingController
  let service: DocumentBundleService
  let subscription: Subscription | undefined

  beforeEach(() => {
    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(DocumentBundleService)
  })

  afterEach(() => {
    subscription?.unsubscribe()
    httpTestingController.verify()
  })

  it('creates a bundle from document ids', () => {
    subscription = service.createFromDocuments([1, 2]).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/`
    )
    expect(req.request.method).toBe('POST')
    expect(req.request.body).toEqual({ documents: [1, 2] })
    req.flush({})
  })

  it('adds a document to a bundle', () => {
    subscription = service.addDocument(4, 7, 'schedule').subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/4/documents/`
    )
    expect(req.request.method).toBe('POST')
    expect(req.request.body).toEqual({
      document: 7,
      bundle_item_name: 'schedule',
    })
    req.flush({})
  })

  it('updates a membership name', () => {
    subscription = service.updateMembership(4, 9, 'terms').subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/4/documents/9/`
    )
    expect(req.request.method).toBe('PATCH')
    expect(req.request.body).toEqual({ bundle_item_name: 'terms' })
    req.flush({})
  })

  it('removes a membership', () => {
    subscription = service.removeMembership(4, 9).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/4/documents/9/`
    )
    expect(req.request.method).toBe('DELETE')
    req.flush({})
  })

  it('reorders memberships', () => {
    subscription = service.reorder(4, [9, 8]).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/4/order/`
    )
    expect(req.request.method).toBe('PATCH')
    expect(req.request.body).toEqual({ membership_ids: [9, 8] })
    req.flush({})
  })
})
