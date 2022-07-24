from email.utils import localtime
from azure.mgmt.compute import ComputeManagementClient
from azure.identity import AzureCliCredential
import sys

resource_group = 'xcc-assessment-efi'
subscription_id = '31169275-2308-4cdd-8d7a-f39ffd65bbf8'


def create_client(subscription_id):
    credential = AzureCliCredential()
    compute_client = ComputeManagementClient(credential, subscription_id)

    return compute_client

def fetch_vms(resource_group, subscription_id):
    compute_client = create_client(subscription_id)
    instances = [vm for vm in compute_client.virtual_machines.list(resource_group_name = resource_group)]

    return instances

def fetch_snapshots(resource_group, subscription_id):
    compute_client = create_client(subscription_id)
    snapshots = [snapshot for snapshot in compute_client.snapshots.list_by_resource_group(resource_group_name = resource_group)]

    return snapshots

compute_client = create_client(subscription_id)

#Getting the first command line argument (if exists) to run the requested subprocess
try:
    subprocess_name = sys.argv[1]

    #Checking what subprocess will execute
    #BACKUP -2 creating a snapshot for all primary disks of vms with label ‘backup’ set to ‘true
    if(subprocess_name == "snapshot"):
        print("Starting backup process")
        print("Found " + str(len(fetch_vms(resource_group, subscription_id))) + " instances")
        
        #Getting info about vms
        for vm in fetch_vms(resource_group, subscription_id):
            print("Instance: " + vm.name +"-instance")
            print("Backup Enabled: " + vm.tags['backup']) 

            #Checking each vm if a snapshot had been created 
            if vm.tags['backup'] == 'true':
                for snapshot in fetch_snapshots(resource_group, subscription_id):  
                    
                    print("Last Backup was " + str((localtime()-snapshot.time_created)) + " ago")

                    #Checking if the snapshot had been created less than 24 hours ago
                    if ((localtime()-snapshot.time_created).total_seconds() < 86400): 
                        print("Skipping backup creation since the last backup is too recent")
                    
                    else:    
                        print("Starting asynchronous backup creation")
                        
                        managed_disk = compute_client.disks.get(resource_group, vm.storage_profile.os_disk.name)
                        
                        #Creating asynchronous backup
                        async_snapshot_creation = compute_client.snapshots.begin_create_or_update(
                            resource_group,
                            snapshot.name,
                            {
                                'location': vm.location,
                                'creation_data': {
                                    'create_option': 'Copy',
                                    'source_uri': managed_disk.id
                                }
                            }
                            )
                        snapshot = async_snapshot_creation.result()

                        #Changing the vm's backup tag after creating a snapshot
                        vm.tags['backup'] = 'true'
        else:

            print("Snapshot for disk " + vm.name + "-instance is Status")

    #BACKUP -3 Removing old backups according to the retention policy
    elif(subprocess_name == "apply-retention-policy"):
        
        print("Checking backups against retention policy")

        #List of vms
        for vm in fetch_vms(resource_group, subscription_id):
            print("Checking backups for disk " + vm.name)

            #List of snapshots to get date and name 
            for snapshot in fetch_snapshots(resource_group, subscription_id):
                date = snapshot.time_created.date()
                name = snapshot.name

                #Second list of snapshots for comparing their dates
                for snapshot in fetch_snapshots(resource_group, subscription_id):

                    #No more than one backup per day should be kept (last 7 days)
                    #Checking if two diffent snapshots created the same day
                    if (date == snapshot.time_created.date()) & (name != snapshot.name):

                        print("Deleting snapshot" + snapshot.name)
                        #Deleting the snapshots of the second list that had been created 
                        #the same day as the snapshot of the first list 
                        compute_client.snapshots.begin_delete(
                        resource_group,
                        snapshot.name
                        )
                
                    #No more than one backup per week should be kept
                    #Checking if two diffent snapshots created the same week
                    elif (date.isocalendar()[1] == snapshot.time_created.date().isocalendar()[1] & (name != snapshot.name)):

                        print("Deleting snapshot" + snapshot.name)
                        #Deleting the snapshots of the second list that had been created 
                        #the same week as the snapshot of the first list
                        compute_client.snapshots.begin_delete(
                        resource_group,
                        snapshot.name
                        )
                    
                    else:

                        print("There is no backups against retention policy")
    else:
        print('Wrong subprocess name')

#if no command line argument exists 
except IndexError: 
    
    #BACKUP -1 Printing vms' info list 
    print ("{:<15} {:<20} {:<15} {:<20}".format('Instance','Backup Enabled','Disk','Last Backup'))
    
    #List of vms
    for vm in fetch_vms(resource_group, subscription_id):
        
        #Checking if a snapshop had been created for each vm
        if (vm.tags['backup'])=='true':
            last_backup = str(vm.time_created)
        else:
            last_backup = 'Never'
        
        #Printing the list with the requested info
        print ("{:<15} {:<20} {:<15} {:<20}".format(vm.name, vm.tags['backup'], vm.storage_profile.os_disk.name, last_backup))
