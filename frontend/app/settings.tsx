import React, { useState } from 'react';
import {
    View,
    Text,
    TextInput,
    TouchableOpacity,
    StyleSheet,
    Alert,
    ActivityIndicator,
    ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useAuth } from '@/contexts/AuthContext';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { Colors } from '@/constants/theme';
import { Ionicons } from '@expo/vector-icons';
import { changePassword, deleteAccount } from '@/services/api';
import { tokenStorage } from '@/services/storage';

export default function SettingsScreen() {
    const router = useRouter();
    const { logout } = useAuth();
    const colorScheme = useColorScheme();
    const colors = Colors[colorScheme ?? 'light'];

    // Change password state
    const [currentPassword, setCurrentPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmNewPassword, setConfirmNewPassword] = useState('');
    const [isChangingPassword, setIsChangingPassword] = useState(false);

    // Delete account state
    const [deletePassword, setDeletePassword] = useState('');
    const [deleteConfirmation, setDeleteConfirmation] = useState('');
    const [isDeletingAccount, setIsDeletingAccount] = useState(false);

    const validatePasswordChange = (): string | null => {
        if (!currentPassword.trim() || !newPassword.trim() || !confirmNewPassword.trim()) {
            return 'Please fill in all password fields';
        }

        if (newPassword.length < 8) {
            return 'New password must be at least 8 characters long';
        }

        if (!/[a-z]/.test(newPassword)) {
            return 'New password must contain at least one lowercase letter';
        }

        if (!/[A-Z]/.test(newPassword)) {
            return 'New password must contain at least one uppercase letter';
        }

        if (!/[0-9]/.test(newPassword)) {
            return 'New password must contain at least one number';
        }

        if (newPassword !== confirmNewPassword) {
            return 'New passwords do not match';
        }

        return null;
    };

    const handleChangePassword = async () => {
        const validationError = validatePasswordChange();
        if (validationError) {
            Alert.alert('Validation Error', validationError);
            return;
        }

        setIsChangingPassword(true);
        try {
            const accessToken = await tokenStorage.getAccessToken();
            if (!accessToken) {
                Alert.alert('Error', 'Please log in again');
                return;
            }

            await changePassword(accessToken, {
                current_password: currentPassword,
                new_password: newPassword,
            });

            Alert.alert(
                'Success',
                'Your password has been changed. Please log in again with your new password.',
                [
                    {
                        text: 'OK',
                        onPress: async () => {
                            await logout();
                        },
                    },
                ]
            );
        } catch (error: any) {
            Alert.alert('Error', error.message || 'Failed to change password');
        } finally {
            setIsChangingPassword(false);
        }
    };

    const handleDeleteAccount = async () => {
        if (!deletePassword.trim()) {
            Alert.alert('Error', 'Please enter your password');
            return;
        }

        if (deleteConfirmation !== 'DELETE') {
            Alert.alert('Error', 'Please type DELETE to confirm');
            return;
        }

        Alert.alert(
            'Delete Account',
            'This action is permanent and cannot be undone. All your data will be deleted.',
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: 'Delete Forever',
                    style: 'destructive',
                    onPress: async () => {
                        setIsDeletingAccount(true);
                        try {
                            const accessToken = await tokenStorage.getAccessToken();
                            if (!accessToken) {
                                Alert.alert('Error', 'Please log in again');
                                return;
                            }

                            await deleteAccount(accessToken, {
                                password: deletePassword,
                                confirmation: deleteConfirmation,
                            });

                            Alert.alert('Account Deleted', 'Your account has been permanently deleted.', [
                                {
                                    text: 'OK',
                                    onPress: async () => {
                                        await logout();
                                    },
                                },
                            ]);
                        } catch (error: any) {
                            Alert.alert('Error', error.message || 'Failed to delete account');
                        } finally {
                            setIsDeletingAccount(false);
                        }
                    },
                },
            ]
        );
    };

    return (
        <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
            <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
                {/* Header */}
                <View style={styles.header}>
                    <TouchableOpacity
                        onPress={() => router.back()}
                        style={[styles.backButton, { backgroundColor: colorScheme === 'dark' ? '#252525' : '#f5f5f5' }]}
                    >
                        <Ionicons name="arrow-back" size={24} color={colors.text} />
                    </TouchableOpacity>
                    <Text style={[styles.headerTitle, { color: colors.text }]}>Settings</Text>
                    <View style={styles.headerSpacer} />
                </View>

                <View style={styles.content}>
                    {/* Change Password Section */}
                    <View style={[styles.section, { backgroundColor: colorScheme === 'dark' ? '#1a1a1a' : '#fff', borderColor: colors.icon + '30' }]}>
                        <View style={styles.sectionHeader}>
                            <View style={[styles.sectionIconContainer, { backgroundColor: colors.tint + '20' }]}>
                                <Ionicons name="key" size={20} color={colors.tint} />
                            </View>
                            <Text style={[styles.sectionTitle, { color: colors.text }]}>Change Password</Text>
                        </View>

                        <View style={styles.inputContainer}>
                            <View style={[styles.inputWrapper, { backgroundColor: colorScheme === 'dark' ? '#252525' : '#f5f5f5', borderColor: colors.icon + '30' }]}>
                                <Ionicons name="lock-closed-outline" size={20} color={colors.icon} style={styles.inputIcon} />
                                <TextInput
                                    style={[styles.input, { color: colors.text }]}
                                    placeholder="Current password"
                                    placeholderTextColor={colors.icon}
                                    value={currentPassword}
                                    onChangeText={setCurrentPassword}
                                    secureTextEntry
                                    autoCapitalize="none"
                                    editable={!isChangingPassword}
                                />
                            </View>
                        </View>

                        <View style={styles.inputContainer}>
                            <View style={[styles.inputWrapper, { backgroundColor: colorScheme === 'dark' ? '#252525' : '#f5f5f5', borderColor: colors.icon + '30' }]}>
                                <Ionicons name="lock-open-outline" size={20} color={colors.icon} style={styles.inputIcon} />
                                <TextInput
                                    style={[styles.input, { color: colors.text }]}
                                    placeholder="New password"
                                    placeholderTextColor={colors.icon}
                                    value={newPassword}
                                    onChangeText={setNewPassword}
                                    secureTextEntry
                                    autoCapitalize="none"
                                    editable={!isChangingPassword}
                                />
                            </View>
                            <Text style={[styles.hint, { color: colors.icon }]}>
                                8+ chars with uppercase, lowercase & number
                            </Text>
                        </View>

                        <View style={styles.inputContainer}>
                            <View style={[styles.inputWrapper, { backgroundColor: colorScheme === 'dark' ? '#252525' : '#f5f5f5', borderColor: colors.icon + '30' }]}>
                                <Ionicons name="shield-checkmark-outline" size={20} color={colors.icon} style={styles.inputIcon} />
                                <TextInput
                                    style={[styles.input, { color: colors.text }]}
                                    placeholder="Confirm new password"
                                    placeholderTextColor={colors.icon}
                                    value={confirmNewPassword}
                                    onChangeText={setConfirmNewPassword}
                                    secureTextEntry
                                    autoCapitalize="none"
                                    editable={!isChangingPassword}
                                />
                            </View>
                        </View>

                        <TouchableOpacity
                            style={[styles.button, isChangingPassword && styles.buttonDisabled]}
                            onPress={handleChangePassword}
                            disabled={isChangingPassword}
                        >
                            {isChangingPassword ? (
                                <ActivityIndicator color="#fff" />
                            ) : (
                                <>
                                    <Text style={styles.buttonText}>Update Password</Text>
                                    <Ionicons name="checkmark-circle" size={20} color="#fff" style={styles.buttonIcon} />
                                </>
                            )}
                        </TouchableOpacity>
                    </View>

                    {/* Delete Account Section */}
                    <View style={[styles.section, styles.dangerSection, { backgroundColor: colorScheme === 'dark' ? '#1a1a1a' : '#fff', borderColor: '#ef4444' + '50' }]}>
                        <View style={styles.sectionHeader}>
                            <View style={[styles.sectionIconContainer, { backgroundColor: '#ef4444' + '20' }]}>
                                <Ionicons name="trash" size={20} color="#ef4444" />
                            </View>
                            <Text style={[styles.sectionTitle, { color: colors.text }]}>Delete Account</Text>
                        </View>

                        <Text style={[styles.dangerText, { color: colors.icon }]}>
                            This will permanently delete your account and all associated data including your travel history, achievements, and settings. This action cannot be undone.
                        </Text>

                        <View style={styles.inputContainer}>
                            <View style={[styles.inputWrapper, { backgroundColor: colorScheme === 'dark' ? '#252525' : '#f5f5f5', borderColor: colors.icon + '30' }]}>
                                <Ionicons name="lock-closed-outline" size={20} color={colors.icon} style={styles.inputIcon} />
                                <TextInput
                                    style={[styles.input, { color: colors.text }]}
                                    placeholder="Enter your password"
                                    placeholderTextColor={colors.icon}
                                    value={deletePassword}
                                    onChangeText={setDeletePassword}
                                    secureTextEntry
                                    autoCapitalize="none"
                                    editable={!isDeletingAccount}
                                />
                            </View>
                        </View>

                        <View style={styles.inputContainer}>
                            <View style={[styles.inputWrapper, { backgroundColor: colorScheme === 'dark' ? '#252525' : '#f5f5f5', borderColor: colors.icon + '30' }]}>
                                <Ionicons name="warning-outline" size={20} color="#ef4444" style={styles.inputIcon} />
                                <TextInput
                                    style={[styles.input, { color: colors.text }]}
                                    placeholder='Type "DELETE" to confirm'
                                    placeholderTextColor={colors.icon}
                                    value={deleteConfirmation}
                                    onChangeText={setDeleteConfirmation}
                                    autoCapitalize="characters"
                                    editable={!isDeletingAccount}
                                />
                            </View>
                        </View>

                        <TouchableOpacity
                            style={[styles.deleteButton, isDeletingAccount && styles.buttonDisabled]}
                            onPress={handleDeleteAccount}
                            disabled={isDeletingAccount}
                        >
                            {isDeletingAccount ? (
                                <ActivityIndicator color="#fff" />
                            ) : (
                                <>
                                    <Ionicons name="trash-outline" size={20} color="#fff" style={styles.deleteButtonIcon} />
                                    <Text style={styles.deleteButtonText}>Delete My Account</Text>
                                </>
                            )}
                        </TouchableOpacity>
                    </View>
                </View>
            </ScrollView>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    scrollView: {
        flex: 1,
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: 16,
        paddingVertical: 12,
    },
    backButton: {
        width: 40,
        height: 40,
        borderRadius: 12,
        justifyContent: 'center',
        alignItems: 'center',
    },
    headerTitle: {
        fontSize: 18,
        fontWeight: '600',
    },
    headerSpacer: {
        width: 40,
    },
    content: {
        padding: 16,
    },
    section: {
        borderRadius: 16,
        padding: 20,
        borderWidth: 1,
        marginBottom: 20,
    },
    dangerSection: {
        borderWidth: 1,
    },
    sectionHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: 20,
    },
    sectionIconContainer: {
        width: 36,
        height: 36,
        borderRadius: 10,
        justifyContent: 'center',
        alignItems: 'center',
        marginRight: 12,
    },
    sectionTitle: {
        fontSize: 18,
        fontWeight: '600',
    },
    inputContainer: {
        marginBottom: 16,
    },
    inputWrapper: {
        flexDirection: 'row',
        alignItems: 'center',
        height: 52,
        borderWidth: 1,
        borderRadius: 12,
        paddingHorizontal: 16,
    },
    inputIcon: {
        marginRight: 12,
    },
    input: {
        flex: 1,
        fontSize: 16,
        height: '100%',
    },
    hint: {
        fontSize: 12,
        marginTop: 6,
        marginLeft: 4,
    },
    button: {
        backgroundColor: '#10b981',
        height: 52,
        borderRadius: 12,
        flexDirection: 'row',
        justifyContent: 'center',
        alignItems: 'center',
        marginTop: 4,
    },
    buttonDisabled: {
        opacity: 0.6,
    },
    buttonText: {
        color: '#fff',
        fontSize: 16,
        fontWeight: '600',
    },
    buttonIcon: {
        marginLeft: 8,
    },
    dangerText: {
        fontSize: 14,
        lineHeight: 20,
        marginBottom: 20,
    },
    deleteButton: {
        backgroundColor: '#ef4444',
        height: 52,
        borderRadius: 12,
        flexDirection: 'row',
        justifyContent: 'center',
        alignItems: 'center',
        marginTop: 4,
    },
    deleteButtonIcon: {
        marginRight: 8,
    },
    deleteButtonText: {
        color: '#fff',
        fontSize: 16,
        fontWeight: '600',
    },
});
